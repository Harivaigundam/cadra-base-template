"""Composition root for the Larkspur / Saguaro patient-communication system.

Wires the Clean Architecture layers together::

    interface  ->  application  ->  domain
    infrastructure adapters are injected at the edges (Dependency Inversion).

The architecture follows ``architecture-diagram.md``: channels converge on a
gateway, an identity & safety layer gates every turn, the AI workflow
orchestrator routes to controlled tools, and only allowlisted tools touch the
backend. Highly confidential language-model work stays on a self-hosted model
(see ``Internet-search.md`` for the vendor/approach comparison).

Run the scenario demo::

    python -m src.solution
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .application.identity import IdentityService
from .application.orchestrator import WorkflowOrchestrator
from .application.ports import Services
from .application.safety import SafetyService
from .application.workflows import (
    AdminFaqWorkflow,
    DischargeWorkflow,
    InsuranceWorkflow,
    PriorAuthWorkflow,
    RefillWorkflow,
    ResultsWorkflow,
    SchedulingWorkflow,
)
from .domain.model import CallerContext, Channel, Intent, Language, WorkflowResult
from .infrastructure.ai import (
    ApiModel,
    KeywordSpeechToText,
    ModelRouter,
    SelfHostedModel,
    SimpleTextToSpeech,
)
from .infrastructure.backend import (
    BusinessCalendar,
    ConsoleNotifier,
    InMemoryAudit,
    InMemoryEpic,
    InMemoryEscalation,
    InMemoryPayer,
    InMemoryPriorAuth,
    SimpleMonitoring,
    SystemClock,
)
from .interface.channels import ChannelGateway

#: Seed data for the in-memory Epic adapter.
DEFAULT_PATIENTS: dict = {
    "P-1001": {"phone": "+16025550101", "coverage": {"plan": "Humana Medicare Advantage", "active": True}},
    "P-1002": {"phone": "+16025550102", "coverage": {"plan": "Medicare", "active": True}},
    "P-1003": {"phone": "+16025550103", "coverage": {"plan": "Self-pay", "active": False}},
}


@dataclass
class Application:
    """A fully wired application instance (used for running or testing)."""

    orchestrator: WorkflowOrchestrator
    gateway: ChannelGateway
    services: Services


def build_application(patients: Optional[dict] = None, prior_auth: Optional[dict] = None) -> Application:
    """Build the application with in-memory (fake) adapters.

    Args:
        patients: Optional Epic patient seed data keyed by patient id.
        prior_auth: Optional (patient_id, procedure) -> status mapping.

    Returns:
        A wired :class:`Application`.
    """
    services = Services(
        epic=InMemoryEpic(patients or DEFAULT_PATIENTS),
        payer=InMemoryPayer(),
        prior_auth=InMemoryPriorAuth(prior_auth or {("P-1002", "MRI"): "approved"}),
        notifier=ConsoleNotifier(),
        audit=InMemoryAudit(),
        escalation=InMemoryEscalation(),
        monitoring=SimpleMonitoring(),
        calendar=BusinessCalendar(),
        clock=SystemClock(),
        model=ModelRouter(self_hosted=SelfHostedModel(), api=ApiModel()),
    )

    workflows = {
        Intent.RESULTS: ResultsWorkflow(),
        Intent.REFILL: RefillWorkflow(),
        Intent.INSURANCE: InsuranceWorkflow(),
        Intent.PRIOR_AUTH: PriorAuthWorkflow(),
        Intent.SCHEDULE: SchedulingWorkflow(),
        Intent.RESCHEDULE: SchedulingWorkflow(),
        Intent.DISCHARGE_FOLLOWUP: DischargeWorkflow(),
        Intent.ADMIN_FAQ: AdminFaqWorkflow(),
    }

    orchestrator = WorkflowOrchestrator(
        safety=SafetyService(),
        identity=IdentityService(),
        workflows=workflows,
        services=services,
    )
    gateway = ChannelGateway(stt=KeywordSpeechToText(), tts=SimpleTextToSpeech())
    return Application(orchestrator=orchestrator, gateway=gateway, services=services)


def run_turn(
    app: Application,
    label: str,
    text: str,
    context: CallerContext,
    provided: Optional[dict] = None,
) -> WorkflowResult:
    """Handle one caller turn and echo the rendered (spoken/text) reply."""
    result = app.orchestrator.handle(text, context, provided)
    rendered = app.gateway.render(context.channel, result.message, context.language)
    print(f"[{label}] {context.channel.value}/{context.language.value} -> {result.disposition.value}")
    print(f"    reply: {rendered}")
    return result


def main() -> None:
    """Demonstrate the five assessment scenarios A-E end to end."""
    app = build_application()
    print("Larkspur Health / Saguaro Family Medicine - patient communication demo\n")
    verified = {"name": "Maria", "dob": "1954-06-02"}

    # Case A - refill request + insurance change (voice, verified by name + DOB).
    ctx_a = CallerContext(channel=Channel.VOICE, patient_id="P-1001")
    run_turn(app, "A-refill", "I need a refill for my lisinopril", ctx_a, verified)
    run_turn(app, "A-insurance", "Does my new Humana plan cover this?", ctx_a, verified)

    # Case B - worsening heart-failure symptoms (emergency escalation).
    run_turn(app, "B-emergency", "I have worsening shortness of breath and swelling", CallerContext(channel=Channel.VOICE))

    # Case C - Spanish MRI prior-authorization inquiry for a spouse (representative).
    ctx_c = CallerContext(
        channel=Channel.VOICE,
        language=Language.ES,
        patient_id="P-1002",
        subject_patient_id="P-1002",
        is_authorized_representative=True,
    )
    run_turn(app, "C-spanish-mri", "Quiero el estado de la autorizacion de la MRI", ctx_c, verified)

    # Case D - unknown SMS asking for A1C results (no disclosure).
    run_turn(app, "D-sms-a1c", "What was my A1C result?", CallerContext(channel=Channel.SMS))

    # Case E - winter visitor asking for a Mesa appointment.
    run_turn(app, "E-visitor", "I am a winter visitor, can I get an appointment in Mesa?", CallerContext(channel=Channel.VOICE))

    print("\nSummary")
    print("  interactions       :", app.services.monitoring.counters.get("interaction", 0))
    print("  disclosure_blocked :", app.services.monitoring.counters.get("disclosure_blocked", 0))
    print("  escalations        :", len(app.services.escalation.tickets))
    print("  staff tasks        :", len(app.services.epic.tasks))
    print("  audit events       :", len(app.services.audit.events))


if __name__ == "__main__":
    main()
