"""Test suite for the Larkspur Health patient-communication solution.

Coverage is intentionally minimal but meaningful:

* Unit tests   - domain policies, model routing, identity, one workflow.
* Integration  - orchestrator end to end with in-memory adapters (Cases A/B/E).
* Security     - SMS PHI never disclosed (Case D); highly confidential data
                 stays on the self-hosted model; third-party access control.

Run::

    python -m pytest -q test.py          # or
    python -m unittest -v test
"""
from __future__ import annotations

import unittest

from src.application.identity import IdentityService
from src.application.workflows import RefillWorkflow
from src.domain.model import (
    CallerContext,
    Channel,
    DataClass,
    Disposition,
    Intent,
    Language,
    SafetyTier,
    VerificationLevel,
    WorkflowRequest,
)
from src.domain.policies import DisclosurePolicy, RedFlagPolicy
from src.infrastructure.ai import ApiModel, ModelRouter, SelfHostedModel
from src.solution import build_application


# --- Unit: red-flag screening ---------------------------------------------

class RedFlagPolicyTests(unittest.TestCase):
    def test_emergency_sign_is_detected(self):
        result = RedFlagPolicy().assess("worsening shortness of breath and swelling", Language.EN)
        self.assertIs(result.tier, SafetyTier.EMERGENCY)
        self.assertIn("911", result.guidance or "")

    def test_emergency_guidance_is_localized_spanish(self):
        result = RedFlagPolicy().assess("tengo dolor de pecho", Language.ES)
        self.assertIs(result.tier, SafetyTier.EMERGENCY)
        self.assertIn("911", result.guidance or "")

    def test_routine_request_has_no_flags(self):
        result = RedFlagPolicy().assess("I would like to book an appointment", Language.EN)
        self.assertIs(result.tier, SafetyTier.ROUTINE)


# --- Unit: disclosure control --------------------------------------------

class DisclosurePolicyTests(unittest.TestCase):
    def test_sms_never_discloses_phi(self):
        allowed, _ = DisclosurePolicy().can_disclose(
            Channel.SMS, VerificationLevel.AUTHENTICATED, DataClass.CONFIDENTIAL
        )
        self.assertFalse(allowed)

    def test_highly_confidential_requires_authenticated(self):
        policy = DisclosurePolicy()
        self.assertFalse(policy.can_disclose(Channel.VOICE, VerificationLevel.BASIC, DataClass.HIGHLY_CONFIDENTIAL)[0])
        self.assertTrue(policy.can_disclose(Channel.VOICE, VerificationLevel.AUTHENTICATED, DataClass.HIGHLY_CONFIDENTIAL)[0])

    def test_public_information_always_allowed(self):
        self.assertTrue(DisclosurePolicy().can_disclose(Channel.SMS, VerificationLevel.NONE, DataClass.PUBLIC)[0])


# --- Unit: model routing (self-hosted vs API) -----------------------------

class ModelRouterTests(unittest.TestCase):
    def test_highly_confidential_stays_self_hosted(self):
        router = ModelRouter(SelfHostedModel(), ApiModel())
        output = router.generate("x", DataClass.HIGHLY_CONFIDENTIAL)
        self.assertEqual(router.last_target, "self_hosted")
        self.assertIn("self-hosted", output)

    def test_lower_sensitivity_uses_api(self):
        router = ModelRouter(SelfHostedModel(), ApiModel())
        router.generate("x", DataClass.CONFIDENTIAL)
        self.assertEqual(router.last_target, "api")


# --- Unit: identity verification ------------------------------------------

class IdentityServiceTests(unittest.TestCase):
    def test_portal_session_is_authenticated(self):
        ctx = CallerContext(channel=Channel.PORTAL_CHAT, portal_authenticated=True, patient_id="P-1")
        self.assertIs(IdentityService().verify(ctx, {}).level, VerificationLevel.AUTHENTICATED)

    def test_name_and_dob_is_basic(self):
        ctx = CallerContext(channel=Channel.VOICE, patient_id="P-1")
        result = IdentityService().verify(ctx, {"name": "A", "dob": "1960-01-01"})
        self.assertIs(result.level, VerificationLevel.BASIC)

    def test_no_evidence_is_unverified(self):
        self.assertFalse(IdentityService().verify(CallerContext(channel=Channel.VOICE), {}).passed)

    def test_third_party_requires_authorization(self):
        service = IdentityService()
        representative = CallerContext(
            channel=Channel.VOICE, patient_id="P-1", subject_patient_id="P-2",
            is_authorized_representative=True,
        )
        stranger = CallerContext(channel=Channel.VOICE, patient_id="P-1", subject_patient_id="P-2")
        self.assertTrue(service.is_authorized_for_subject(representative))
        self.assertFalse(service.is_authorized_for_subject(stranger))


# --- Unit: a workflow (refill is a request, never a prescription) ----------

class RefillWorkflowTests(unittest.TestCase):
    def test_refill_creates_task_for_clinical_review(self):
        app = build_application()
        ctx = CallerContext(channel=Channel.VOICE, patient_id="P-1001")
        result = RefillWorkflow().handle(WorkflowRequest(Intent.REFILL, ctx, "refill lisinopril"), app.services)
        self.assertIs(result.disposition, Disposition.STAFF_TASK)
        self.assertIn("clinical review", result.message.lower())
        self.assertEqual(len(app.services.epic.tasks), 1)


# --- Integration + security: end-to-end turns ------------------------------

class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.app = build_application()

    def test_case_a_refill_and_insurance(self):
        verified = {"name": "Maria", "dob": "1954-06-02"}
        ctx = CallerContext(channel=Channel.VOICE, patient_id="P-1001")
        refill = self.app.orchestrator.handle("I need a refill for my lisinopril", ctx, verified)
        insurance = self.app.orchestrator.handle("Does my new Humana plan cover this?", ctx, verified)
        self.assertIs(refill.disposition, Disposition.STAFF_TASK)
        self.assertIs(insurance.disposition, Disposition.AUTO_RESOLVED)

    def test_case_b_emergency_escalates_to_human(self):
        result = self.app.orchestrator.handle(
            "worsening shortness of breath and swelling", CallerContext(channel=Channel.VOICE)
        )
        self.assertIs(result.disposition, Disposition.EMERGENCY_GUIDANCE)
        self.assertTrue(result.escalated)
        self.assertEqual(len(self.app.services.escalation.tickets), 1)

    def test_case_e_unknown_appointment_becomes_staff_task(self):
        result = self.app.orchestrator.handle(
            "I am a winter visitor, can I get an appointment in Mesa?",
            CallerContext(channel=Channel.VOICE),
        )
        self.assertIs(result.disposition, Disposition.STAFF_TASK)

    def test_audit_trail_is_written(self):
        self.app.orchestrator.handle("book an appointment", CallerContext(channel=Channel.VOICE))
        self.assertGreaterEqual(len(self.app.services.audit.events), 1)


# --- Security: PHI protection ---------------------------------------------

class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.app = build_application()

    def test_case_d_sms_result_request_is_blocked(self):
        result = self.app.orchestrator.handle("What was my A1C result?", CallerContext(channel=Channel.SMS))
        self.assertIs(result.disposition, Disposition.BLOCKED)
        self.assertNotIn("a1c", result.message.lower())

    def test_sms_insurance_request_is_blocked(self):
        result = self.app.orchestrator.handle("is my insurance active", CallerContext(channel=Channel.SMS))
        self.assertIs(result.disposition, Disposition.BLOCKED)

    def test_verified_voice_disclosure_is_allowed(self):
        ctx = CallerContext(channel=Channel.VOICE, patient_id="P-1001")
        result = self.app.orchestrator.handle(
            "is my insurance active", ctx, {"name": "Maria", "dob": "1954-06-02"}
        )
        self.assertIs(result.disposition, Disposition.AUTO_RESOLVED)


if __name__ == "__main__":
    unittest.main()
