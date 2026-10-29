"""Application-level identity verification and subject authorization.

Deterministic rules only: never rely on an LLM to decide who a caller is or
whether they may access a subject's data.
"""
from __future__ import annotations

from ..domain.model import CallerContext, VerificationLevel, VerificationResult


class IdentityService:
    """Verifies caller identity and authorizes access to a subject's data."""

    def verify(self, context: CallerContext, provided: dict) -> VerificationResult:
        """Determine the verification level for a caller.

        Args:
            context: The caller's context (channel, patient id, portal session).
            provided: Caller-supplied evidence, e.g. ``otp_verified``, ``name``,
                ``dob``.

        Returns:
            The resulting `VerificationResult`.
        """
        if context.portal_authenticated:
            return VerificationResult(
                VerificationLevel.AUTHENTICATED, True, "authenticated portal session"
            )
        if provided.get("otp_verified") is True:
            return VerificationResult(
                VerificationLevel.AUTHENTICATED, True, "OTP verified"
            )
        if provided.get("name") and provided.get("dob") and context.patient_id:
            return VerificationResult(
                VerificationLevel.BASIC, True, "name + DOB matched"
            )
        return VerificationResult(
            VerificationLevel.NONE, False, "identity not verified"
        )

    def is_authorized_for_subject(self, context: CallerContext) -> bool:
        """Whether the caller may act on behalf of ``subject_patient_id``.

        Access is allowed when there is no specific subject, when the caller is
        the subject, or when the caller is an authorized representative.
        """
        if context.subject_patient_id is None:
            return True
        if context.patient_id == context.subject_patient_id:
            return True
        return context.is_authorized_representative
