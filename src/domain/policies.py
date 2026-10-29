"""Clinician-approved, deterministic policies (never LLM-only).

Red-flag screening and disclosure control are pure rules so they are testable
and auditable, per the architecture decision in APPROACH.md Section C.
"""
from __future__ import annotations

from .model import (
    Channel,
    DataClass,
    Language,
    SafetyAssessment,
    SafetyTier,
    VerificationLevel,
)

# Emergency warning signs -> approved guidance, per language (clinician-approved).
EMERGENCY_RULES: dict[str, dict[Language, str]] = {
    "chest pain": {
        Language.EN: "This may be an emergency. Call 911 now.",
        Language.ES: "Esto puede ser una emergencia. Llame al 911 ahora.",
    },
    "shortness of breath": {
        Language.EN: "This may be an emergency. Call 911 or go to the ER now.",
        Language.ES: "Esto puede ser una emergencia. Llame al 911 o vaya a urgencias ahora.",
    },
    "difficulty breathing": {
        Language.EN: "This may be an emergency. Call 911 now.",
        Language.ES: "Esto puede ser una emergencia. Llame al 911 ahora.",
    },
    "swelling": {
        Language.EN: "New or worsening swelling with breathlessness may be an emergency. Call 911.",
        Language.ES: "La hinchazon nueva o que empeora con falta de aire puede ser una emergencia. Llame al 911.",
    },
    "severe bleeding": {
        Language.EN: "This may be an emergency. Call 911 now.",
        Language.ES: "Esto puede ser una emergencia. Llame al 911 ahora.",
    },
    "suicidal": {
        Language.EN: "You are not alone. Call or text 988 now.",
        Language.ES: "No esta solo. Llame o envie un mensaje al 988 ahora.",
    },
    # Spanish aliases (30% of patients prefer Spanish; safety screening is bilingual).
    "dolor de pecho": {
        Language.EN: "This may be an emergency. Call 911 now.",
        Language.ES: "Esto puede ser una emergencia. Llame al 911 ahora.",
    },
    "falta de aire": {
        Language.EN: "This may be an emergency. Call 911 or go to the ER now.",
        Language.ES: "Esto puede ser una emergencia. Llame al 911 o vaya a urgencias ahora.",
    },
    "dificultad para respirar": {
        Language.EN: "This may be an emergency. Call 911 now.",
        Language.ES: "Esto puede ser una emergencia. Llame al 911 ahora.",
    },
    "hinchazon": {
        Language.EN: "New or worsening swelling with breathlessness may be an emergency. Call 911.",
        Language.ES: "La hinchazon nueva o que empeora con falta de aire puede ser una emergencia. Llame al 911.",
    },
    "sangrado": {
        Language.EN: "This may be an emergency. Call 911 now.",
        Language.ES: "Esto puede ser una emergencia. Llame al 911 ahora.",
    },
}

# Urgent (non-emergency) signs -> same-day human follow-up.
URGENT_RULES: dict[str, dict[Language, str]] = {
    "fever": {
        Language.EN: "A nurse will follow up with you today.",
        Language.ES: "Una enfermera le llamara hoy.",
    },
    "dizziness": {
        Language.EN: "A nurse will follow up with you today.",
        Language.ES: "Una enfermera le llamara hoy.",
    },
    "fiebre": {
        Language.EN: "A nurse will follow up with you today.",
        Language.ES: "Una enfermera le llamara hoy.",
    },
    "mareo": {
        Language.EN: "A nurse will follow up with you today.",
        Language.ES: "Una enfermera le llamara hoy.",
    },
}


class RedFlagPolicy:
    """Screens text for urgent/emergency warning signs using approved rules only."""

    def assess(self, text: str, language: Language) -> SafetyAssessment:
        lowered = text.lower()
        for flag, guidance in EMERGENCY_RULES.items():
            if flag in lowered:
                return SafetyAssessment(SafetyTier.EMERGENCY, (flag,), guidance[language])
        for flag, guidance in URGENT_RULES.items():
            if flag in lowered:
                return SafetyAssessment(SafetyTier.URGENT, (flag,), guidance[language])
        return SafetyAssessment(SafetyTier.ROUTINE)


class DisclosurePolicy:
    """Decides whether protected data may be disclosed for a channel + verification level."""

    def can_disclose(
        self, channel: Channel, level: VerificationLevel, data_class: DataClass
    ) -> tuple[bool, str]:
        if data_class is DataClass.PUBLIC:
            return True, "public information"
        # SMS is an unverified channel: never disclose protected information.
        if channel is Channel.SMS:
            return False, "SMS is unverified; route to an authenticated channel"
        if data_class is DataClass.HIGHLY_CONFIDENTIAL:
            if level is VerificationLevel.AUTHENTICATED:
                return True, "authenticated"
            return False, "highly confidential data requires authenticated verification"
        if level in (VerificationLevel.BASIC, VerificationLevel.AUTHENTICATED):
            return True, "verified"
        return False, "identity not verified"
