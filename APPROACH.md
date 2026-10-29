# Approach — AI Patient Communication System for Saguaro Family Medicine

## Problem & Context

Larkspur Health is designing a unified voice, SMS, and portal-chat assistant for Saguaro Family
Medicine (14 clinics across AZ/NV/NM; ~75,000 patients; ~2,800 calls/day; >40% Medicare; ~30%
prefer Spanish). The first clinic must reach a controlled launch within eight weeks. The design
below is constrained, policy-driven, and safety-first; the linked diagram in Section C shows the
components and relationships.

## Section A — Questions

Prioritized by architectural significance. Each question lists why it matters and how the answer
changes the design.

**Q1. Which Epic capabilities and interfaces are licensed and approved for programmatic use
(patient lookup, Cadence scheduling, MyChart messaging, refill requests, Real-Time Eligibility,
ADT discharge notifications)?**
- *Why it matters:* Epic is the system of record and the largest scope driver; most automatable
  value depends on what Epic will actually let us read and write.
- *Design impact:* If only read access or task creation is available, scheduling/refill/eligibility
  become "collect details + create a staff task" instead of "confirm a transaction," which changes
  the orchestrator and the Section D launch scope.

**Q2. What is Saguaro's clinician-approved escalation protocol — red-flag symptom criteria, who
owns the urgent queue, expected response time, and after-hours/holiday routing?**
- *Why it matters:* Patient safety and Case B depend on a defined, owned pathway; the AI must never
  let a routine callback delay urgent care.
- *Design impact:* Directly defines the safety-screening rules, handoff SLAs, on-call integration,
  and whether automated screening may run at all.

**Q3. What identity-verification standard does Larkspur/Saguaro require before protected information
is disclosed on phone, SMS, and portal channels?**
- *Why it matters:* HIPAA and Cases A, C, and D hinge on preventing unauthorized disclosure; SMS
  numbers are inherently unverified.
- *Design impact:* Determines the verification challenge set, which fields may be confirmed, and
  whether any PHI can be spoken versus routed to the portal.

**Q4. How are legally authorized representatives (spouse, parent, caregiver) recorded and verified
in Epic, and what authorization must be captured before discussing a third party's record?**
- *Why it matters:* Case C (spouse MRI inquiry) requires confirming the caller's *authority*, not
  just their identity.
- *Design impact:* Defines the proxy-access model, verification evidence, and audit requirements;
  without it, third-party inquiries must route to staff.

**Q5. Which clinical and administrative data sources sit outside Epic (payer eligibility
clearinghouse, imaging centers, prior-authorization portals, hospital ADT feed)?**
- *Why it matters:* MRI/prior-authorization status and eligibility often live outside Epic, and we
  must not assume availability.
- *Design impact:* Determines whether we build direct integrations, rely on Epic interfaces, or
  generate staff tasks for unconfirmed statuses.

**Q6. What are the approved audio, transcription, and retention policies, and which state consent
rules apply (AZ/NV/NM)?**
- *Why it matters:* Privacy and BAA obligations, plus two-party-consent considerations, govern
  whether audio may be recorded and how long data persists.
- *Design impact:* Sets recording/consent prompts, redaction, retention/TTL, and logging design, and
  may forbid storing raw audio entirely.

**Q7. What are the scheduling rules — appointment types, new vs. established patient,
provider/location matching, insurance eligibility prechecks, and waitlist behavior?**
- *Why it matters:* Case E requires offering a valid appointment or a callback without
  mis-scheduling; a wrong slot creates downstream harm.
- *Design impact:* Decides whether automated booking is enabled at launch or deferred (Section D),
  and how eligibility gates scheduling.

**Q8. Which telephony, SMS, and existing portal-chat platforms are in place, and may we integrate
with or must we replace them?**
- *Why it matters:* Integrate-versus-replace changes cost, timeline, and number-porting risk.
- *Design impact:* Defines the channel-gateway adapters, the SMS secure-link strategy, and vendor
  ownership/roles.

**Q9. What are the clinic business hours, holiday calendars, time zones, and current after-hours
coverage model per site?**
- *Why it matters:* After-hours routing, the two-business-day discharge-follow-up deadline, and
  appointment-slot logic all depend on accurate calendars.
- *Design impact:* Determines routing rules, calendar integration, and deadline computation.

**Q10. What languages and dialects must be supported, and what is the human-interpreter fallback
vendor and SLA?**
- *Why it matters:* ~30% of patients prefer Spanish, and clinical ASR/TTS accuracy is variable.
- *Design impact:* Sets ASR/TTS language coverage, confidence thresholds, and the interpreter
  handoff path.

**Q11. What are the pilot's success metrics and acceptance thresholds, and how will workload
reduction and safety be measured?**
- *Why it matters:* Go/no-go and value proof need agreed, measurable criteria.
- *Design impact:* Drives monitoring, audit instrumentation, the evaluation harness, and Section D's
  acceptance criteria.

**Q12. What AI governance, data-security, and vendor constraints apply — data residency, model
hosting, no-training-on-PHI, BAA coverage, prompt/log retention, and the protection of highly
confidential ("top secret") data? May patient data be sent to third-party LLM APIs?**
- *Why it matters:* Compliance and procurement filter which ASR/LLM/TTS vendors are eligible; some
  data must never leave the organization's trust boundary, and routing protected or highly sensitive
  data to external, API-based LLMs creates disclosure, data-residency, and vendor-risk exposure.
- *Design impact:* Constrains vendor selection. For highly confidential data we run an **LLM hosted
  on our own servers** (self-hosted / open-weight) instead of an external API integration; only
  lower-sensitivity or de-identified workloads may use approved, BAA-covered API models. This adds
  GPU hosting, model-ops, and update-cadence responsibility and shapes the model-routing layer in
  Section C.

## Section B — Assumptions

**AS-1. Epic exposes approved FHIR/HL7 interfaces** for patient lookup, scheduling, task creation,
and permitted status retrieval, with read/write scopes.
- *Why reasonable:* The brief mandates secure Epic integration and lists these functions.
- *If incorrect:* Workflows degrade to "collect and create a staff task"; automated booking is
  deferred and Section D scope narrows to intake, routing, and escalation.

**AS-2. Saguaro has — or will provision — a licensed contact-center/telephony platform and a
business SMS number we can integrate**, rather than build channels from scratch.
- *Why reasonable:* The brief lists voice, SMS, and portal chat as existing channels.
- *If incorrect:* Number provisioning/porting and SMS-vendor onboarding add weeks and cost.

**AS-3. The pilot clinic is an Arizona site (Mesa/Phoenix area) on Epic**, consistent with Case E's
Mesa-area scheduling.
- *Why reasonable:* Cases reference Mesa and Arizona is the largest region.
- *If incorrect:* Scheduling/payer/calendar logic, languages, and pilot metrics change.

**AS-4. Audio is not retained by default; transcripts are stored only where policy allows**, under a
signed BAA.
- *Why reasonable:* The brief demands clear audio processing and retention policies; a privacy-first
  default is safest.
- *If incorrect:* Storage, consent capture, redaction, and retention controls must be added before
  launch.

**AS-5. A staffed human queue with named clinical and administrative owners exists during pilot
hours**, with an after-hours escalation path.
- *Why reasonable:* Safe handoff requires humans, and the current answering service is a known pain
  point to improve.
- *If incorrect:* Launch is blocked for safety-sensitive flows.

**AS-6. Clinician-approved content libraries** (red-flag criteria, emergency guidance scripts,
administrative FAQs) are provided and maintained.
- *Why reasonable:* The AI must use approved language and must not improvise clinical content.
- *If incorrect:* Safety screening and answer automation cannot go live; only routing and task
  capture remain.

**AS-7. SMS is treated as an unverified channel**; sensitive information is delivered only via an
approved secure channel (e.g., an authenticated portal link).
- *Why reasonable:* Phone numbers are not identity (Case D).
- *If incorrect:* Disclosure risk and legal exposure rise; SMS scope narrows to non-sensitive
  coordination only.

**AS-8. Portal chat reuses the existing authenticated patient session** and inherits its
authorization controls.
- *Why reasonable:* Reusing established portal auth avoids a parallel identity system.
- *If incorrect:* A separate authentication and consent flow is required.

**AS-9. Payer eligibility and prior-authorization status are retrievable from an authoritative
source** (Epic Real-Time Eligibility or a clearinghouse), not manually maintained.
- *Why reasonable:* Cases A and C require authoritative status answers.
- *If incorrect:* Eligibility/authorization inquiries become staff tasks carrying stated uncertainty.

**AS-10. English/Spanish ASR and TTS meet a clinically accepted accuracy bar** and hand off to a
human interpreter on low confidence.
- *Why reasonable:* The organization needs bilingual support and must avoid miscommunication.
- *If incorrect:* Spanish automation is limited to scripted intents with human interpreter fallback.

## Section C — Solution Design

**Unified channels.** A single **channel gateway** fronts inbound **voice**, **SMS**, and **portal
chat** through channel-specific adapters, normalizing each into one conversation/session model.
This ensures safety, verification, and audit policies are enforced once and identically across all
channels rather than per-channel.

**Voice processing and conversational AI.** Streaming **speech-to-text** converts live speech;
a dialog/response layer generates replies only from **clinician-approved content** and tool
results; **text-to-speech** returns natural responses. Raw audio is not persisted by default.

**AI orchestration and workflow routing.** A **policy-driven workflow orchestrator** — not an
unrestricted agent — classifies intent, runs safety screening first, then routes to controlled
workflows (scheduling, refill, insurance, prior-authorization, and discharge follow-up, whose
two-business-day outreach deadline is computed against the clinic's business calendar). This matches
the assessment's stated decision: *a constrained, policy-driven workflow is preferable to
unrestricted autonomous agents for sensitive clinical tasks*. The LLM interprets patient language;
**policy and authorized tools decide actions**. A **model-routing layer** sends highly confidential
data only to an **LLM hosted on our own servers** (self-hosted / open-weight); only lower-sensitivity
workloads may use approved, BAA-covered API models.

**Agent responsibilities and autonomy boundaries.** A **conversational agent** handles intake, FAQ,
and clarification only. A **safety agent** applies approved red-flag screening and triggers
emergency guidance/escalation. **Workflow agents** call allowlisted tools with validated arguments.
**Humans** diagnose, prescribe, approve escalations, and resolve ambiguity. The AI never diagnoses,
never independently authorizes prescriptions, never modifies records outside allowlisted tools, and
never discloses PHI before verification.

**Patient authentication and authorization.** Portal chat reuses the authenticated portal session;
voice/SMS require an approved verification challenge against recorded details before any PHI
disclosure; third-party access requires an **authorized-representative** check. All disclosures are
role- and permission-gated and audited.

**Epic integration.** Approved APIs/interfaces for patient lookup, scheduling, task creation, and
permitted status retrieval. Integration failures degrade gracefully to staff task creation with
captured context; there are no direct database writes.

**Clinical safety and escalation.** Safety screening runs **before** routine flows. Urgent/red-flag
cases receive clinician-approved emergency guidance (including calling emergency services when
indicated) and immediate human escalation; unresolved or low-confidence cases transfer with full
context to **prioritized staff queues**. Red-flag detection uses **deterministic,
clinician-approved rules** — never the LLM alone — and the assistant stays outside
clinical-decision-support scope, providing navigation and approved guidance only (no diagnosis or
treatment recommendation). Routine requests never delay urgent ones.

**Multilingual communication.** English and Spanish end-to-end on **every channel and workflow** —
voice, SMS, and portal chat, and scheduling, refill, insurance, prior-authorization, and discharge
follow-up. Language is auto-detected with patient override; SMS/portal responses use bilingual
templates; low ASR confidence or out-of-scope intents hand off to a **human interpreter** via a
bilingual staff queue. Safety-critical guidance is delivered in the patient's language.

**Patient data protection and audio handling.** PHI is encrypted in transit and at rest, with
least-privilege access. Raw audio is not stored by default; retention is configurable per approved
policy. A consent/disclosure notice plays on entry, and all access and AI actions are audited. Because one
pilot state (Nevada) requires all-party consent for call recording, all-party consent is captured on
every call regardless of location.
Vendors are BAA-covered, and highly confidential data is processed only by the self-hosted model —
never sent to external API vendors.

**Reliability, fallback, and monitoring.** Circuit breakers and timeouts protect Epic calls; on
failure, context is captured and routed to staff, and after-hours calls fall back to on-call. Every
interaction is monitored for latency, containment, escalation, disclosure events, and safety
outcomes, feeding alerting and incident response.

**Patient scenarios A–E.**
- **Case A — Refill and insurance change:** verify identity → create a **lisinopril refill request
  for clinical review** (no authorization) → separately query the new **Humana** plan's eligibility
  from the authoritative source. Do not guarantee coverage; ambiguous/absent results become a staff
  task.
- **Case B — Worsening heart-failure symptoms:** treat dyspnea + swelling as **potentially urgent**
  → deliver clinician-approved emergency guidance (including calling emergency services when
  indicated) → trigger **immediate urgent escalation**. No diagnosis; a routine callback must not
  delay care.
- **Case C — Spanish MRI inquiry:** respond in **Spanish** → verify the caller's **authority** to
  access the spouse's information → retrieve the MRI prior-authorization status if available, else
  create a staff follow-up task. No disclosure without authorization.
- **Case D — Unknown SMS requesting A1C results:** do **not** disclose based on name and date of
  birth → direct the sender to the authenticated portal or an approved verification process.
- **Case E — Winter visitor requesting an appointment:** collect new-patient details → run
  clinician-defined urgent-warning screening → check **Mesa-area** scheduling and eligibility →
  offer an appropriate appointment or staff callback. Never infer location from the phone area code.

Every scenario is delivered in the patient's **preferred language (English or Spanish)** — including
the safety-critical emergency guidance in Case B — not only when Spanish is explicitly raised.

**Architecture diagram:** [Mermaid — renders on GitHub](./architecture-diagram.md) ·
[draw.io — editable source](./architecture-diagram.drawio).

## Section D — Eight-Week Scope

| Timeline | Delivery focus |
| --- | --- |
| Weeks 1–2 | Confirm workflows, privacy/retention policy, patient-verification standard, staff ownership, and Epic access & scopes; stand up environments and approved content libraries. |
| Weeks 3–4 | Implement pilot voice/chat intake, administrative FAQs, safety screening, and staff escalation paths. |
| Weeks 5–6 | Validate permitted scheduling and refill-request workflows, SMS safeguards, and English/Spanish support. |
| Weeks 7–8 | Test all patient scenarios A–E, conduct staff training, monitor pilot traffic, and complete safety and operational acceptance checks. |

**Launch at one clinic.** Basic phone/chat support, approved administrative answers,
appointment-request handling, refill intake, secure identity verification, multilingual fallback,
and reliable human escalation. **Automated scheduling is enabled only after** the integration and
workflow rules pass validation.

**Requires validation before go-live:** Epic interface scopes and write permissions; identity
verification standard; clinical escalation protocol and red-flag criteria; audio/retention policy
and consent; SMS secure-disclosure path; interpreter fallback SLA; staff-queue ownership.

**Deferred:** autonomous clinical advice; complex prior-authorization decisions; broad cross-clinic
rollout; automated outbound discharge campaigns; and independent prescription authorization.

**Critical dependencies:** Epic API access/scopes — production access requires a **sponsoring
provider and interface review** (write scopes need extra approval; lead times are typically weeks to
months); telephony/SMS platform integration; signed BAAs
with ASR/LLM/TTS vendors; approved clinical content; and a staffed escalation queue.

**Risks and mitigations:** missed or unsafe escalation (clinician-approved screening + immediate
human handoff); PHI disclosure (verification, channel policy, and auditing); ASR accuracy, especially
in Spanish (confidence thresholds + interpreter); integration failure (graceful fallback to staff
tasks); and scope creep (explicit defer list).

**Acceptance criteria:** no unauthorized health-information disclosure in testing; no missed
simulated emergency escalation; successful human fallback; measurable reduction in routine staff
workload; and complete auditability. Exact thresholds are agreed with Saguaro before launch.

## Section E — Next Step

If the assessment runs out of time, the next action is to validate this design against Saguaro's
clinical escalation policies, Epic integration capabilities, privacy requirements, and pilot
acceptance criteria.

## Appendix — Reference Documents & Artefacts

- **Official assessment brief (source requirements):** [`reference/design.docx`](./reference/design.docx)
  — the 16 architecture/workflow requirements and patient scenarios A–E.
- **Architecture brief:** [`reference/architect.docx`](./reference/architect.docx) — component
  purposes, the constrained-workflow decision, the eight-week plan, and Section E.
- **Architecture diagram (Mermaid, renders on GitHub):** [`architecture-diagram.md`](./architecture-diagram.md).
- **Architecture diagram (draw.io, editable):** [`architecture-diagram.drawio`](./architecture-diagram.drawio).
- **Internet research & architecture comparison:** [`Internet-search.md`](./Internet-search.md).

### Conformance to reference requirements (`reference/design.docx`)

| # | Reference requirement | Where addressed |
| --- | --- | --- |
| 1 | Unified channel gateway | C — Unified channels |
| 2 | Voice processing; no raw audio by default | C — Voice processing; Privacy |
| 3 | Portal authentication reuses session | C — Patient authentication |
| 4 | SMS treated as unverified | C — Patient authentication; Case D; AS-7 |
| 5 | Multilingual EN/ES with human fallback | C — Multilingual |
| 6 | Safety-first screening | C — Clinical safety and escalation |
| 7 | Intent orchestration to controlled workflows | C — AI orchestration |
| 8 | Identity and consent before disclosure | C — Patient authentication |
| 9 | Constrained AI actions (allowlisted tools) | C — Agent responsibilities |
| 10 | Epic integration via approved APIs | C — Epic integration |
| 11 | Scheduling eligibility and slot checks | C — Case E; D |
| 12 | Medication refill intake (no prescribing) | C — Case A; Agent boundaries |
| 13 | Insurance / authorization status routing | C — Cases A and C |
| 14 | Discharge follow-up within two business days | C — AI orchestration; D |
| 15 | Human handoff, reliability, encryption, audit | C — Clinical safety; Reliability; Privacy |
| 16 | Patient scenarios A–E | C — Patient scenarios A–E |

The `reference/architect.docx` components — channel gateway, speech-to-text/text-to-speech, safety and
identity layer, AI workflow orchestrator, Epic integration, human escalation queue, secure storage and
audit, and monitoring — are all present in `architecture-diagram.md` / `architecture-diagram.drawio`.

### External references consulted (web research)

- Call-recording consent by state — AZ one-party, NM one-party, NV all-party:
  [Justia 50-state survey](https://www.justia.com/50-state-surveys/recording-phone-calls-and-conversations/),
  [RCFP — Nevada](https://www.rcfp.org/reporters-recording-guide/nevada/).
- HIPAA Business Associate Agreements:
  [HHS](https://www.hhs.gov/hipaa/for-professionals/privacy/guidance/business-associates/index.html).
- Epic on FHIR (scheduling `Appointment.$find`/`$book`, `Patient.Search`, `Coverage`, `Communication`)
  and HL7 v2 ADT discharge notifications:
  [fhir.epic.com](https://fhir.epic.com/Specifications), [open.epic.com](https://open.epic.com/interface/hl7v2).
- FDA Clinical Decision Support Software guidance (staying out of device scope):
  [FDA](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software).
- ONC HTI-1 (algorithm transparency) and NIST AI RMF:
  [healthit.gov](https://healthit.gov/resources/hti-1-at-a-glance/),
  [NIST](https://www.nist.gov/itl/ai-risk-management-framework).
- HIPAA-eligible AI APIs vs self-hosting:
  [AWS HIPAA-eligible services](https://aws.amazon.com/compliance/hipaa-eligible-services-reference/),
  [Azure OpenAI data privacy](https://learn.microsoft.com/en-us/azure/ai-foundry/responsible-ai/openai/data-privacy).
