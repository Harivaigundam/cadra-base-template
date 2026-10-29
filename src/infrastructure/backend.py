"""In-memory adapters implementing the application ports.

This module contains lightweight, dependency-free infrastructure adapters used
for local development and testing. Each adapter satisfies a ``Protocol`` defined
in :mod:`src.application.ports` and uses only domain types from
:mod:`src.domain.model`.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from ..application.ports import (
    AuditPort,
    CalendarPort,
    ClockPort,
    EpicPort,
    EscalationPort,
    MonitoringPort,
    NotificationPort,
    PayerPort,
    PriorAuthPort,
)
from ..domain.model import AuditEvent, Channel, EscalationTicket


class SystemClock(ClockPort):
    """Real wall-clock time source."""

    def now(self) -> datetime:
        """Return the current local date and time."""
        return datetime.now()


class BusinessCalendar(CalendarPort):
    """Calendar that counts only weekdays (Mon-Fri)."""

    def add_business_days(self, start: datetime, days: int) -> datetime:
        """Return ``start`` advanced by ``days`` business days.

        Saturdays and Sundays are skipped. Negative ``days`` moves backwards.
        """
        current = start
        step = 1 if days >= 0 else -1
        remaining = abs(days)
        while remaining > 0:
            current = current + timedelta(days=step)
            if current.weekday() < 5:  # Monday == 0 ... Friday == 4
                remaining -= 1
        return current


class InMemoryEpic(EpicPort):
    """In-memory EHR backend keyed by patient id."""

    def __init__(self, patients: Optional[dict] = None) -> None:
        """Initialize with an optional ``patient_id -> record`` mapping."""
        self.patients: dict = patients or {}
        self.tasks: list[dict] = []
        self._appointment_seq = 0

    def find_patient_id(self, phone: str) -> Optional[str]:
        """Return the patient id whose recorded phone matches ``phone``."""
        for patient_id, record in self.patients.items():
            if record.get("phone") == phone:
                return patient_id
        return None

    def get_coverage(self, patient_id: str) -> dict:
        """Return the coverage dict for a patient, else inactive coverage."""
        record = self.patients.get(patient_id)
        if record and record.get("coverage"):
            return record["coverage"]
        return {"active": False}

    def book_appointment(self, patient_id: str, when: datetime, location: str) -> str:
        """Book an appointment and return a new incrementing appointment id."""
        self._appointment_seq += 1
        return f"APPT-{self._appointment_seq:04d}"

    def create_task(
        self, patient_id: Optional[str], summary: str, priority: str
    ) -> str:
        """Create a staff task and return a new incrementing task id."""
        self.tasks.append(
            {"patient_id": patient_id, "summary": summary, "priority": priority}
        )
        return f"TASK-{len(self.tasks):04d}"


class InMemoryPayer(PayerPort):
    """In-memory payer eligibility checker."""

    def check_eligibility(self, patient_id: str, plan: str) -> dict:
        """Return eligibility for ``plan``; unknown when plan is empty."""
        if not plan:
            return {"plan": "unknown", "active": False, "status": "unknown"}
        return {"plan": plan, "active": True, "status": "active"}


class InMemoryPriorAuth(PriorAuthPort):
    """In-memory prior-authorization status store."""

    def __init__(self, known: Optional[dict] = None) -> None:
        """Initialize with a ``(patient_id, procedure) -> status`` mapping."""
        self.known: dict = known or {}

    def get_status(self, patient_id: str, procedure: str) -> dict:
        """Return the known status for a procedure, else ``unknown``."""
        status = self.known.get((patient_id, procedure), "unknown")
        return {"procedure": procedure, "status": status}


class ConsoleNotifier(NotificationPort):
    """Notifier that records outgoing messages in memory."""

    def __init__(self) -> None:
        """Initialize an empty outbox."""
        self.sent: list[dict] = []

    def send(self, channel: Channel, to: str, message: str) -> None:
        """Record a notification for the given channel and recipient."""
        self.sent.append({"channel": channel, "to": to, "message": message})


class InMemoryAudit(AuditPort):
    """Audit sink that stores events in memory."""

    def __init__(self) -> None:
        """Initialize an empty event log."""
        self.events: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> None:
        """Append an audit event to the in-memory log."""
        self.events.append(event)


class InMemoryEscalation(EscalationPort):
    """Escalation queue that stores tickets in memory."""

    def __init__(self) -> None:
        """Initialize an empty ticket queue."""
        self.tickets: list[EscalationTicket] = []

    def enqueue(self, ticket: EscalationTicket) -> str:
        """Queue a ticket and return a new incrementing escalation id."""
        self.tickets.append(ticket)
        return f"ESC-{len(self.tickets):04d}"


class SimpleMonitoring(MonitoringPort):
    """Monitoring sink that accumulates counters in memory."""

    def __init__(self) -> None:
        """Initialize an empty counter map."""
        self.counters: dict[str, float] = {}

    def emit(self, name: str, value: float = 1.0) -> None:
        """Increment the named counter by ``value``."""
        self.counters[name] = self.counters.get(name, 0.0) + value
