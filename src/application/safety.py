"""Application-level safety screening.

Thin service that delegates red-flag screening to the deterministic, clinician
approved `RedFlagPolicy`. The application layer owns orchestration; the rules
themselves live in the domain so they stay testable and auditable.
"""
from __future__ import annotations

from ..domain.model import Language, SafetyAssessment
from ..domain.policies import RedFlagPolicy


class SafetyService:
    """Screens caller text for urgent/emergency warning signs."""

    def __init__(self, policy: RedFlagPolicy | None = None) -> None:
        """Create the service.

        Args:
            policy: Red-flag policy to delegate to. Defaults to a new
                `RedFlagPolicy`.
        """
        self._policy = policy if policy is not None else RedFlagPolicy()

    def assess(self, text: str, language: Language) -> SafetyAssessment:
        """Assess `text` for safety tier in the caller's `language`."""
        return self._policy.assess(text, language)
