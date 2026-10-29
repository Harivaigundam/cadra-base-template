"""Workflow use cases — application layer.

Each workflow implements the ``WorkflowPort`` protocol: a class-level ``intent``
and a ``handle`` method that turns a ``WorkflowRequest`` into a ``WorkflowResult``
using injected ``Services``. No I/O is performed here directly; all side effects
go through ports.
"""
from __future__ import annotations

from ..domain.model import (
    DataClass,
    Disposition,
    Intent,
    WorkflowRequest,
    WorkflowResult,
)
from .ports import Services


class ResultsWorkflow:
    """Handles requests for lab/test results without disclosing them (Case D).

    Results are protected information: over an unverified channel such as SMS
    the caller is directed to the secure, authenticated portal rather than given
    values. Disclosure control in the orchestrator enforces this.
    """

    intent: Intent = Intent.RESULTS

    def handle(self, request: WorkflowRequest, services: Services) -> WorkflowResult:
        """Return a protected-data result that never contains the actual values."""
        return WorkflowResult(
            Disposition.STAFF_TASK,
            "For your privacy, please view your results in the secure patient "
            "portal, or a staff member will assist you.",
            data_class=DataClass.CONFIDENTIAL,
        )


class AdminFaqWorkflow:
    """Answers administrative questions that carry no PHI."""

    intent: Intent = Intent.ADMIN_FAQ

    def handle(self, request: WorkflowRequest, services: Services) -> WorkflowResult:
        """Return public clinic hours and after-hours guidance."""
        return WorkflowResult(
            Disposition.AUTO_RESOLVED,
            "Our clinics are open Mon-Fri 8am-5pm; after hours a nurse line is available.",
            DataClass.PUBLIC,
        )


class SchedulingWorkflow:
    """Books appointments for covered patients, else files a staff task."""

    intent: Intent = Intent.SCHEDULE

    def handle(self, request: WorkflowRequest, services: Services) -> WorkflowResult:
        """Attempt to auto-book; fall back to a staff callback task."""
        location = request.entities.get("location", "Mesa")
        patient_id = request.context.patient_id

        coverage = (
            services.epic.get_coverage(patient_id) if patient_id else {}
        )

        if patient_id and coverage.get("active") is True:
            when = services.calendar.add_business_days(services.clock.now(), 3)
            conf = services.epic.book_appointment(patient_id, when, location)
            return WorkflowResult(
                Disposition.AUTO_RESOLVED,
                f"Your appointment is booked (confirmation {conf}).",
                DataClass.CONFIDENTIAL,
                details={"confirmation": conf, "location": location},
            )

        services.epic.create_task(
            patient_id, "New/unscheduled appointment request", "routine"
        )
        return WorkflowResult(
            Disposition.STAFF_TASK,
            "We received your appointment request; a staff member will call you.",
        )


class RefillWorkflow:
    """Routes refill requests to clinical review as a staff task."""

    intent: Intent = Intent.REFILL

    def handle(self, request: WorkflowRequest, services: Services) -> WorkflowResult:
        """Create a clinical-review task; never authorizes a prescription."""
        task = services.epic.create_task(
            request.context.patient_id, "Refill request for clinical review", "routine"
        )
        return WorkflowResult(
            Disposition.STAFF_TASK,
            "Your refill request was submitted for clinical review. This is a "
            "request only and is not a prescription authorization.",
            DataClass.CONFIDENTIAL,
            details={"task_id": task},
        )


class InsuranceWorkflow:
    """Reports eligibility/coverage status without guaranteeing coverage."""

    intent: Intent = Intent.INSURANCE

    def handle(self, request: WorkflowRequest, services: Services) -> WorkflowResult:
        """Check payer eligibility and summarize the plan status."""
        plan = request.entities.get("plan", "unknown")
        info = services.payer.check_eligibility(request.context.patient_id, plan)
        msg = f"Plan {info.get('plan', plan)}: {info.get('status', 'unknown')}."
        return WorkflowResult(
            Disposition.AUTO_RESOLVED,
            msg + " Coverage is not guaranteed until confirmed by staff.",
            DataClass.CONFIDENTIAL,
            details=info,
        )


class PriorAuthWorkflow:
    """Reports prior-auth status when known, else files a follow-up task."""

    intent: Intent = Intent.PRIOR_AUTH

    def handle(self, request: WorkflowRequest, services: Services) -> WorkflowResult:
        """Return a known prior-auth status or defer to staff follow-up."""
        procedure = request.entities.get("procedure", "MRI")
        info = services.prior_auth.get_status(request.context.patient_id, procedure)

        if info.get("status") in ("approved", "pending", "denied"):
            return WorkflowResult(
                Disposition.AUTO_RESOLVED,
                f"{procedure} prior authorization status: {info['status']}.",
                DataClass.CONFIDENTIAL,
                details=info,
            )

        services.epic.create_task(
            request.context.patient_id,
            f"Prior-auth status lookup: {procedure}",
            "routine",
        )
        return WorkflowResult(
            Disposition.STAFF_TASK,
            f"The {procedure} authorization status is not available yet; a staff "
            "member will follow up.",
        )


class DischargeWorkflow:
    """Schedules a nurse follow-up call within two business days."""

    intent: Intent = Intent.DISCHARGE_FOLLOWUP

    def handle(self, request: WorkflowRequest, services: Services) -> WorkflowResult:
        """Create a high-priority discharge follow-up task and notify the caller."""
        deadline = services.calendar.add_business_days(services.clock.now(), 2)
        task = services.epic.create_task(
            request.context.patient_id,
            f"Hospital-discharge follow-up due {deadline.date().isoformat()}",
            "high",
        )
        return WorkflowResult(
            Disposition.STAFF_TASK,
            f"A nurse will call you within two business days (by "
            f"{deadline.date().isoformat()}).",
            DataClass.CONFIDENTIAL,
            details={"task_id": task, "deadline": deadline.isoformat()},
        )
