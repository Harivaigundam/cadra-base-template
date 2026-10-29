# Internet Search — Research & Architecture Comparison

Linked from [`APPROACH.md`](./APPROACH.md). This file holds the external research used to design the
Larkspur Health / Saguaro Family Medicine system and compares **our architecture** against current
industry best practice, highlighting which option is best.

## 1. Research areas and key sources

**Privacy, consent, and telecom**
- Call-recording consent by state: **Arizona one-party, New Mexico one-party, Nevada all-party** →
  capture all-party consent on every call. (Justia; RCFP)
- A voice-AI vendor handling PHI is a business associate → **signed BAA mandatory**; no HIPAA-fixed
  retention period, but state medical-record rules apply. (HHS)
- Healthcare SMS: **treat the number as unverified**; deliver PHI only via secure, authenticated
  links. (TCPA/HIPAA guidance)

**Epic integration**
- on-FHIR: `Appointment.$find`/`$book`, `Patient.Search`, `Coverage`, `Communication`; HL7 v2 ADT
  (A01/A03/A04) for discharge notifications. (fhir.epic.com; open.epic.com)
- Production requires a **sponsoring provider**; write scopes get extra review; lead times weeks–months.

**Voice stack**
- BAA-covered cloud STT/TTS: Deepgram, AssemblyAI, Azure, Google, ElevenLabs, OpenAI.
- Open-weight / self-hostable: Whisper, Llama, Mistral (Voxtral), Qwen.
- Real-time UX: VAD/turn detection and cancel-in-flight-TTS for barge-in.

**Safety**
- Deterministic **red-flag rules** (never the LLM alone); human-in-the-loop; stay out of FDA
  clinical-decision-support scope; ONC HTI-1 transparency; NIST AI RMF.

**LLM hosting for highly confidential data**
- Self-hosting removes the *model* vendor from the PHI flow (infra host still needs a BAA); vs
  BAA-covered API + zero-data-retention; hybrid = self-host PHI work, de-identify before external APIs.

## 2. Comparison — our architecture vs industry best practice

| Decision area | Our architecture | Industry best practice | Best choice & verdict |
| --- | --- | --- | --- |
| Channel gateway | One gateway for voice + SMS + portal chat | Single BAA-covered CPaaS (Twilio / Amazon Connect) | **Best: one BAA CPaaS.** Matches ours; consolidate on one vendor for one BAA and one audit trail. |
| Real-time voice | Streaming STT → orchestrated dialog → TTS | Streaming cascade with semantic-VAD barge-in; speech-to-speech only for lowest latency | **Best: cascade** (auditable, policy-swappable). Matches ours; add barge-in handling. |
| Orchestration | Constrained, policy-driven workflows | Deterministic workflows; LLM only for NLU/phrasing | **Best: constrained (ours).** Identical; unrestricted agents can't be clinically validated. |
| Identity | Portal session; voice/SMS verification; SMS unverified | Phone: banked ANI + challenge; SMS: OTP/MFA before any PHI | **Best: OTP/MFA before PHI.** Ours aligns; make OTP/MFA explicit. |
| Epic integration | Approved FHIR/HL7 APIs, task fallback | HL7 v2 ADT for events + SMART on FHIR for reads/writes | **Best: ADT + FHIR (ours).** Watch sponsor + lead-time risk. |
| Escalation / after-hours | Prioritized staff queues; off-hours on-call | Risk-scored warm transfer with context; hard-route red flags to 911/on-call | **Best: risk-scored warm transfer (ours).** Add explicit risk scoring. |
| PHI privacy / LLM hosting | Self-host LLM for highly confidential; BAA API for lower-sensitivity | BAA API + ZDR for general; self-host only for residency/PHI-heavy | **Best: hybrid.** Ours is *stricter* than baseline — safest for "top secret" data, higher ops cost; keep hybrid to control cost. |

## 3. Overall verdict — which is best

- **Our constrained, safety-first architecture is the best fit** for this clinical use case and
  **matches industry best practice** on channels, orchestration, Epic integration, and escalation.
  An unrestricted autonomous-agent design would be unsafe and hard to validate — it is *not* the best.
- **Recommended refinements (keep, don't replace):** single BAA-covered CPaaS; semantic-VAD barge-in;
  explicit OTP/MFA verification; risk-scored warm transfer; and a **hybrid LLM** model (self-host for
  highly confidential data, BAA API + zero-data-retention for lower-sensitivity workloads).
- The reference architecture (`reference/design.docx`, `reference/architect.docx`) **aligns with ours**;
  no contradicting requirement was found.

## Sources

- Consent by state: [Justia 50-state survey](https://www.justia.com/50-state-surveys/recording-phone-calls-and-conversations/) · [RCFP — Nevada](https://www.rcfp.org/reporters-recording-guide/nevada/)
- HIPAA / BAAs: [HHS](https://www.hhs.gov/hipaa/for-professionals/privacy/guidance/business-associates/index.html)
- CPaaS: [Twilio HIPAA](https://www.twilio.com/en-us/hipaa) · [Amazon Connect Health](https://aws.amazon.com/products/connect/health/)
- Voice stack: [Deepgram architecture](https://deepgram.com/learn/voice-agent-architecture-stt-llm-tts-pipeline-design) · [Retell](https://www.retellai.com/blog/how-real-time-voice-ai-works-stt-llm-tts)
- Epic: [on FHIR](https://fhir.epic.com/Specifications) · [HL7 v2](https://open.epic.com/interface/hl7v2)
- Identity: [Paubox](https://www.paubox.com/blog/secure-identity-verification-methods-in-healthcare-text-messaging) · [Authsignal](https://www.authsignal.com/blog/articles/hipaa-mfa-requirements-and-what-to-do-before-the-final-rule-lands)
- Safety / governance: [FDA CDS](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software) · [ONC HTI-1](https://healthit.gov/resources/hti-1-at-a-glance/) · [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework)
- Escalation: [Observe.AI](https://www.observe.ai/blog/healthcare-call-center-software-ai-agents-for-patient-access)
- LLM hosting: [AWS HIPAA-eligible services](https://aws.amazon.com/compliance/hipaa-eligible-services-reference/) · [Azure OpenAI data privacy](https://learn.microsoft.com/en-us/azure/ai-foundry/responsible-ai/openai/data-privacy)
