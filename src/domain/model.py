"""Domain model — pure business types (Clean Architecture innermost layer).

No I/O, no frameworks, no third-party imports.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Channel(str, Enum):
    VOICE = "voice"
    SMS = "sms"
    PORTAL_CHAT = "portal_chat"


class Language(str, Enum):
    EN = "en"
    ES = "es"


class Intent(str, Enum):
    SCHEDULE = "schedule"
    RESCHEDULE = "reschedule"
    REFILL = "refill"
    INSURANCE = "insurance"
    PRIOR_AUTH = "prior_auth"
    DISCHARGE_FOLLOWUP = "discharge_followup"
    ADMIN_FAQ = "admin_faq"
    RESULTS = "results"


class SafetyTier(str, Enum):
    ROUTINE = "routine"
    URGENT = "urgent"
    EMERGENCY = "emergency"


class Disposition(str, Enum):
    AUTO_RESOLVED = "auto_resolved"
    STAFF_TASK = "staff_task"
    HUMAN_ESCALATION = "human_escalation"
    EMERGENCY_GUIDANCE = "emergency_guidance"
    BLOCKED = "blocked"


class VerificationLevel(str, Enum):
    NONE = "none"
    BASIC = "basic"                  # name + DOB matched; no PHI disclosure
    AUTHENTICATED = "authenticated"  # OTP / authenticated portal session


class DataClass(str, Enum):
    PUBLIC = "public"
    CONFIDENTIAL = "confidential"                  # standard PHI
    HIGHLY_CONFIDENTIAL = "highly_confidential"    # most sensitive


# ---- Errors ---------------------------------------------------------------

class DomainError(Exception):
    """Base class for domain errors."""


class PolicyViolation(DomainError):
    """A safety/disclosure policy blocked the action."""


class VerificationError(DomainError):
    """Identity verification failed."""


class IntegrationError(DomainError):
    """A backend integration (Epic/payer/etc.) failed."""


# ---- Entities -------------------------------------------------------------

@dataclass(frozen=True)
class CallerContext:
    channel: Channel
    language: Language = Language.EN
    phone: Optional[str] = None
    patient_id: Optional[str] = None
    portal_authenticated: bool = False
    is_authorized_representative: bool = False
    subject_patient_id: Optional[str] = None


@dataclass(frozen=True)
class SafetyAssessment:
    tier: SafetyTier
    matched_flags: tuple[str, ...] = ()
    guidance: Optional[str] = None


@dataclass(frozen=True)
class VerificationResult:
    level: VerificationLevel
    passed: bool
    reason: str = ""


@dataclass(frozen=True)
class WorkflowRequest:
    intent: Intent
    context: CallerContext
    text: str
    entities: dict = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowResult:
    disposition: Disposition
    message: str
    data_class: DataClass = DataClass.PUBLIC
    escalated: bool = False
    details: dict = field(default_factory=dict)


@dataclass(frozen=True)
class EscalationTicket:
    reason: str
    tier: SafetyTier
    context: CallerContext
    summary: str
    created_at: datetime


@dataclass(frozen=True)
class AuditEvent:
    action: str
    actor: str
    subject: Optional[str]
    outcome: str
    data_class: DataClass
    at: datetime
