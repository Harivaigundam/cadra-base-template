"""Ports (interfaces) the application depends on.

Adapters in `src/infrastructure` implement these; the application never imports
adapters directly (Dependency Inversion Principle).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol

from ..domain.model import (
    AuditEvent,
    Channel,
    DataClass,
    EscalationTicket,
    Intent,
    Language,
    WorkflowRequest,
    WorkflowResult,
)


class ClockPort(Protocol):
    def now(self) -> datetime: ...


class CalendarPort(Protocol):
    def add_business_days(self, start: datetime, days: int) -> datetime: ...


class SpeechToTextPort(Protocol):
    def transcribe(self, audio: str, language: Language) -> str: ...


class TextToSpeechPort(Protocol):
    def synthesize(self, text: str, language: Language) -> str: ...


class ModelPort(Protocol):
    """Language model. Adapters choose self-hosted vs API by data class."""

    def generate(self, prompt: str, data_class: DataClass) -> str: ...


class EpicPort(Protocol):
    def find_patient_id(self, phone: str) -> Optional[str]: ...
    def get_coverage(self, patient_id: str) -> dict: ...
    def book_appointment(self, patient_id: str, when: datetime, location: str) -> str: ...
    def create_task(self, patient_id: Optional[str], summary: str, priority: str) -> str: ...


class PayerPort(Protocol):
    def check_eligibility(self, patient_id: str, plan: str) -> dict: ...


class PriorAuthPort(Protocol):
    def get_status(self, patient_id: str, procedure: str) -> dict: ...


class NotificationPort(Protocol):
    def send(self, channel: Channel, to: str, message: str) -> None: ...


class AuditPort(Protocol):
    def record(self, event: AuditEvent) -> None: ...


class EscalationPort(Protocol):
    def enqueue(self, ticket: EscalationTicket) -> str: ...


class MonitoringPort(Protocol):
    def emit(self, name: str, value: float = 1.0) -> None: ...


@dataclass
class Services:
    """Container of injected adapters, passed to workflows and the orchestrator."""

    epic: EpicPort
    payer: PayerPort
    prior_auth: PriorAuthPort
    notifier: NotificationPort
    audit: AuditPort
    escalation: EscalationPort
    monitoring: MonitoringPort
    calendar: CalendarPort
    clock: ClockPort
    model: ModelPort


class WorkflowPort(Protocol):
    intent: Intent

    def handle(self, request: WorkflowRequest, services: Services) -> WorkflowResult: ...
