"""Workflow orchestrator — the application-layer entry point for a caller turn.

Ties together safety screening, identity verification, intent classification,
workflow dispatch and disclosure control. All ordering and side effects are
deterministic so the turn is fully auditable (see APPROACH.md Section C).
"""
from __future__ import annotations

from typing import Optional

from ..domain.model import (
    AuditEvent,
    CallerContext,
    Channel,
    DataClass,
    Disposition,
    EscalationTicket,
    Intent,
    Language,
    SafetyTier,
    WorkflowRequest,
    WorkflowResult,
)
from ..domain.policies import DisclosurePolicy
from .identity import IdentityService
from .ports import Services, WorkflowPort
from .safety import SafetyService


class WorkflowOrchestrator:
    """Coordinates a single inbound turn from safety check to workflow result.

    The orchestrator is the *only* component that knows the full ordering:

    1. emit an interaction metric,
    2. run safety screening,
    3. short-circuit on emergency/urgent tiers,
    4. verify identity,
    5. classify intent and dispatch to a workflow,
    6. enforce disclosure policy on the workflow result.

    Safety and disclosure are pure, clinician-approved rules; the orchestrator
    never lets an LLM make those calls.
    """

    #: Ordered intent rules. Order matters: more specific patterns first so
    #: e.g. "reschedule" is not swallowed by the generic "schedule" keyword.
    _INTENT_RULES: tuple[tuple[Intent, tuple[str, ...]], ...] = (
        (Intent.RESULTS, ("a1c", "lab result", "test result", "results")),
        (Intent.REFILL, ("refill", "lisinopril", "prescription")),
        (Intent.INSURANCE, ("insurance", "plan", "humana")),
        (Intent.PRIOR_AUTH, ("mri", "prior auth", "authorization", "authorisation")),
        (Intent.RESCHEDULE, ("reschedule",)),
        (Intent.DISCHARGE_FOLLOWUP, ("discharge", "hospital")),
        (Intent.SCHEDULE, ("appointment", "schedule", "visit")),
    )

    def __init__(
        self,
        safety: SafetyService,
        identity: IdentityService,
        workflows: dict[Intent, WorkflowPort],
        services: Services,
        disclosure: Optional[DisclosurePolicy] = None,
    ) -> None:
        """Wire the orchestrator with its collaborators and injected adapters.

        Args:
            safety: Screens text for urgent/emergency warning signs.
            identity: Verifies caller identity against the caller context.
            workflows: Intent-to-workflow dispatch table.
            services: Container of injected adapters (ports).
            disclosure: Disclosure policy; defaults to the standard policy.
        """
        self._safety = safety
        self._identity = identity
        self._workflows = workflows
        self.services = services
        self._disclosure = disclosure if disclosure is not None else DisclosurePolicy()

    def classify(self, text: str, language: Language) -> Intent:
        """Map free text to an intent using deterministic keyword rules.

        Args:
            text: Raw caller text (any case).
            language: Caller language; reserved for future localized rules.

        Returns:
            The matched :class:`Intent`, or ``Intent.ADMIN_FAQ`` when nothing
            matches.
        """
        lowered = text.lower()
        for intent, keywords in self._INTENT_RULES:
            for keyword in keywords:
                if keyword in lowered:
                    return intent
        return Intent.ADMIN_FAQ

    def handle(
        self,
        text: str,
        context: CallerContext,
        provided: Optional[dict] = None,
    ) -> WorkflowResult:
        """Process one inbound caller turn end to end.

        Args:
            text: Raw caller text.
            context: Channel, language and caller identity context.
            provided: Optional caller-provided identity claims passed to
                verification.

        Returns:
            The workflow result, possibly replaced by a safety, escalation or
            disclosure outcome.
        """
        self.services.monitoring.emit("interaction", 1.0)

        assessment = self._safety.assess(text, context.language)

        if assessment.tier is SafetyTier.EMERGENCY:
            self.services.escalation.enqueue(
                EscalationTicket(
                    reason="emergency safety flag",
                    tier=SafetyTier.EMERGENCY,
                    context=context,
                    summary=text,
                    created_at=self.services.clock.now(),
                )
            )
            self.services.monitoring.emit("emergency", 1.0)
            self.services.audit.record(
                AuditEvent(
                    action="safety_emergency",
                    actor=context.channel.value,
                    subject=context.patient_id,
                    outcome="escalated",
                    data_class=DataClass.PUBLIC,
                    at=self.services.clock.now(),
                )
            )
            return WorkflowResult(
                Disposition.EMERGENCY_GUIDANCE,
                message=assessment.guidance or "",
                data_class=DataClass.PUBLIC,
                escalated=True,
                details={"flags": list(assessment.matched_flags)},
            )

        if assessment.tier is SafetyTier.URGENT:
            self.services.escalation.enqueue(
                EscalationTicket(
                    reason="urgent safety flag",
                    tier=SafetyTier.URGENT,
                    context=context,
                    summary=text,
                    created_at=self.services.clock.now(),
                )
            )
            self.services.monitoring.emit("urgent", 1.0)
            return WorkflowResult(
                Disposition.HUMAN_ESCALATION,
                message=assessment.guidance or "A nurse will follow up today.",
                escalated=True,
            )

        verification = self._identity.verify(context, provided or {})

        intent = self.classify(text, context.language)
        workflow = self._workflows.get(intent) or self._workflows.get(Intent.ADMIN_FAQ)

        if workflow is None:
            return WorkflowResult(
                Disposition.STAFF_TASK,
                "A staff member will follow up with you.",
            )

        result = workflow.handle(
            WorkflowRequest(intent=intent, context=context, text=text),
            self.services,
        )

        allowed, reason = self._disclosure.can_disclose(
            context.channel, verification.level, result.data_class
        )

        if not allowed:
            self.services.monitoring.emit("disclosure_blocked", 1.0)
            self.services.audit.record(
                AuditEvent(
                    action="disclosure",
                    actor=context.channel.value,
                    subject=context.patient_id,
                    outcome="blocked",
                    data_class=result.data_class,
                    at=self.services.clock.now(),
                )
            )
            if context.channel is Channel.SMS:
                return WorkflowResult(
                    Disposition.BLOCKED,
                    "For your privacy, please use the secure patient portal to "
                    "view this information.",
                )
            self.services.epic.create_task(
                context.patient_id,
                f"Verify identity then assist: {intent.value}",
                "routine",
            )
            return WorkflowResult(
                Disposition.STAFF_TASK,
                "We need to verify your identity first; a staff member will "
                "follow up.",
            )

        self.services.audit.record(
            AuditEvent(
                action="disclosure",
                actor=context.channel.value,
                subject=context.patient_id,
                outcome="ok",
                data_class=result.data_class,
                at=self.services.clock.now(),
            )
        )
        return result
