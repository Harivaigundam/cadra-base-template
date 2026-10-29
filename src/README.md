# `src/` — Solution Explanation

Reference implementation of the Larkspur Health / Saguaro Family Medicine patient-communication
architecture. It is a **design-faithful, runnable** system: real Clean-Architecture structure with
in-memory adapters standing in for Epic, telephony, and models.

- Design: [`../APPROACH.md`](../APPROACH.md) · Diagram: [`../architecture-diagram.md`](../architecture-diagram.md) · Research: [`../Internet-search.md`](../Internet-search.md)
- Entry point: [`solution.py`](./solution.py) · Tests: [`../test.py`](../test.py)

---

## 1. Tech stack & packages

| Item | Choice | Notes |
| --- | --- | --- |
| Language | Python 3.12 | `from __future__ import annotations`, full type hints |
| Runtime deps | **Standard library only** | no third-party imports in `src/` |
| Test runner | `pytest >= 7.4` (also runs under `unittest`) | `../requirements.txt` |
| Style | Clean Architecture + SOLID | dependencies point inward |
| LLM routing | self-hosted vs API by data class | no live model calls (simulated) |
| Epic/payer/telephony | in-memory adapters | ports defined, real adapters plug in |

> `requirements.txt` also retains the starter-template data-science libs (numpy/pandas/scikit-learn/
> scipy/matplotlib/joblib); the solution itself does **not** import them.

**Run:** `python -m src.solution`  ·  **Test:** `python -m pytest -q test.py`

---

## 2. Architecture layers

```
interface  ->  application  ->  domain        (infrastructure implements ports, injected at edges)
```

| Layer | Path | Responsibility |
| --- | --- | --- |
| Domain | `domain/` | Pure model + clinician-approved policies. No I/O. |
| Application | `application/` | Use cases, orchestration, ports (interfaces). |
| Infrastructure | `infrastructure/` | Adapters implementing ports (Epic, models, storage...). |
| Interface | `interface/channels.py` | Channel & Voice Gateway (voice STT/TTS, SMS, portal chat). |
| Composition root | `solution.py` | Wires everything; `build_application()`. |

---

## 3. Domain model — enums

| Enum | Values | Meaning |
| --- | --- | --- |
| `Channel` | `VOICE, SMS, PORTAL_CHAT` | Inbound channel |
| `Language` | `EN, ES` | Conversation language |
| `Intent` | `SCHEDULE, RESCHEDULE, REFILL, INSURANCE, PRIOR_AUTH, DISCHARGE_FOLLOWUP, ADMIN_FAQ, RESULTS` | Classified request |
| `SafetyTier` | `ROUTINE, URGENT, EMERGENCY` | Red-flag screening result |
| `Disposition` | `AUTO_RESOLVED, STAFF_TASK, HUMAN_ESCALATION, EMERGENCY_GUIDANCE, BLOCKED` | Turn outcome |
| `VerificationLevel` | `NONE, BASIC, AUTHENTICATED` | Identity assurance |
| `DataClass` | `PUBLIC, CONFIDENTIAL, HIGHLY_CONFIDENTIAL` | Sensitivity, drives model + disclosure |

## 4. Domain model — dataclasses & errors

| Type | Kind | Key fields |
| --- | --- | --- |
| `CallerContext` | dataclass (frozen) | `channel, language, phone, patient_id, portal_authenticated, is_authorized_representative, subject_patient_id` |
| `SafetyAssessment` | dataclass (frozen) | `tier, matched_flags, guidance` |
| `VerificationResult` | dataclass (frozen) | `level, passed, reason` |
| `WorkflowRequest` | dataclass (frozen) | `intent, context, text, entities` |
| `WorkflowResult` | dataclass (frozen) | `disposition, message, data_class, escalated, details` |
| `EscalationTicket` | dataclass (frozen) | `reason, tier, context, summary, created_at` |
| `AuditEvent` | dataclass (frozen) | `action, actor, subject, outcome, data_class, at` |
| `Services` | dataclass | injected adapters (see ports) |
| `DomainError` / `PolicyViolation` / `VerificationError` / `IntegrationError` | exceptions | error hierarchy |

---

## 5. Policies (deterministic — never LLM-only)

| Policy | File | Behaviour |
| --- | --- | --- |
| `RedFlagPolicy` | `domain/policies.py` | Keyword screening → `EMERGENCY` / `URGENT` / `ROUTINE`; **bilingual** (English + Spanish aliases); returns clinician-approved guidance |
| `DisclosurePolicy` | `domain/policies.py` | `can_disclose(channel, level, data_class)`: **PUBLIC** always; **SMS never** discloses PHI; **HIGHLY_CONFIDENTIAL** requires `AUTHENTICATED`; other PHI requires `BASIC`+ |

---

## 6. Ports (interfaces, `application/ports.py`)

| Port | Methods |
| --- | --- |
| `ClockPort` | `now()` |
| `CalendarPort` | `add_business_days(start, days)` |
| `SpeechToTextPort` | `transcribe(audio, language)` |
| `TextToSpeechPort` | `synthesize(text, language)` |
| `ModelPort` | `generate(prompt, data_class)` |
| `EpicPort` | `find_patient_id, get_coverage, book_appointment, create_task` |
| `PayerPort` | `check_eligibility(patient_id, plan)` |
| `PriorAuthPort` | `get_status(patient_id, procedure)` |
| `NotificationPort` | `send(channel, to, message)` |
| `AuditPort` | `record(event)` |
| `EscalationPort` | `enqueue(ticket)` |
| `MonitoringPort` | `emit(name, value)` |
| `WorkflowPort` | `intent` + `handle(request, services)` |

---

## 7. Application services & workflows

| Component | File | Responsibility |
| --- | --- | --- |
| `SafetyService` | `application/safety.py` | Delegates to `RedFlagPolicy` |
| `IdentityService` | `application/identity.py` | `verify()` (portal / OTP / name+DOB) and `is_authorized_for_subject()` |
| `WorkflowOrchestrator` | `application/orchestrator.py` | Metric → safety → short-circuit → verify → classify+dispatch → disclosure; audits every step |
| Workflows | `application/workflows.py` | `Results, AdminFaq, Scheduling, Refill, Insurance, PriorAuth, Discharge` |

**Workflow behaviour**

| Workflow | Intent | Outcome |
| --- | --- | --- |
| `ResultsWorkflow` | `RESULTS` | Protected; directs to authenticated portal (`CONFIDENTIAL`) |
| `AdminFaqWorkflow` | `ADMIN_FAQ` | Public clinic info (`PUBLIC`) |
| `SchedulingWorkflow` | `SCHEDULE`/`RESCHEDULE` | Books if patient + active coverage, else staff task |
| `RefillWorkflow` | `REFILL` | Creates task for **clinical review** (never a prescription) |
| `InsuranceWorkflow` | `INSURANCE` | Payer eligibility; "coverage not guaranteed" |
| `PriorAuthWorkflow` | `PRIOR_AUTH` | Authorization status, else staff task |
| `DischargeWorkflow` | `DISCHARGE_FOLLOWUP` | Outreach task due **+2 business days** |

---

## 8. Infrastructure adapters & models

| Adapter | Port | Notes |
| --- | --- | --- |
| `SystemClock` | `ClockPort` | `datetime.now()` |
| `BusinessCalendar` | `CalendarPort` | Skips Sat/Sun |
| `InMemoryEpic` | `EpicPort` | Seeded patients; `APPT-/TASK-` ids; `tasks` list |
| `InMemoryPayer` | `PayerPort` | Eligibility stub |
| `InMemoryPriorAuth` | `PriorAuthPort` | Known statuses |
| `ConsoleNotifier` | `NotificationPort` | Records sends |
| `InMemoryAudit` / `InMemoryEscalation` / `SimpleMonitoring` | Audit/Escalation/Monitoring | In-memory stores/counters |
| `SelfHostedModel` / `ApiModel` | `ModelPort` | Prefix outputs for traceability |
| `ModelRouter` | `ModelPort` | **`HIGHLY_CONFIDENTIAL` → self-hosted; else API** (`last_target`) |
| `KeywordSpeechToText` / `SimpleTextToSpeech` | STT/TTS | Simulated, language-aware |
| `ChannelGateway` | interface | Voice → STT/TTS; SMS/portal passthrough |

---

## 9. Runtime flow (one turn)

```
Gateway.intake → Orchestrator.handle
  1 monitoring.emit("interaction")
  2 SafetyService.assess(text, language)         # RedFlagPolicy (EN/ES)
  3 EMERGENCY/URGENT → EscalationPort.enqueue → return guidance
  4 IdentityService.verify(context, provided)
  5 classify(text) → workflow (WorkflowPort)
  6 DisclosurePolicy.can_disclose(channel, level, data_class)
       blocked + SMS  → BLOCKED (redirect to portal)
       blocked + else → EpicPort.create_task → STAFF_TASK
  7 audit each step → WorkflowResult
```

---

## 10. Patient scenarios A–E

| Case | Channel / lang | Result |
| --- | --- | --- |
| A — Refill + insurance change | Voice / EN | Refill → staff task (clinical review); insurance → status, "not guaranteed" |
| B — Worsening heart failure | Voice / EN(ES) | Emergency guidance (911) + immediate human escalation |
| C — Spanish MRI inquiry (spouse) | Voice / **ES** | Representative check → authorization status, else staff task |
| D — Unknown SMS asking A1C | SMS / EN | **BLOCKED** — routed to authenticated portal |
| E — Winter visitor appointment | Voice / EN | Urgent screening → Mesa scheduling/eligibility → appointment or callback |

---

## 11. Security & privacy controls

- **SMS = unverified** — `DisclosurePolicy` blocks all PHI on SMS (Case D).
- **Highly confidential → self-hosted LLM** (`ModelRouter`); standard workloads may use the BAA API.
- **Least privilege / auditability** — allowlisted tools only; every turn audited (`AuditEvent`).
- **Deterministic safety** — red-flag and disclosure decisions are pure rules, not the LLM.
- **Human-in-the-loop** — emergency/urgent and unresolved turns escalate to a prioritized staff queue.

## 12. Tests (`../test.py`, minimal)

| Group | Covers |
| --- | --- |
| Unit | red-flag (EN/ES), disclosure, model routing, identity, refill workflow |
| Integration | Cases A, B, E end-to-end + audit trail |
| Security | Case D SMS blocked; SMS PHI blocked; highly-confidential → self-hosted |

`20 passed`.

## 13. Related documents

| Document | Purpose |
| --- | --- |
| [`../APPROACH.md`](../APPROACH.md) | Sections A–E: questions, assumptions, design, 8-week scope |
| [`../architecture-diagram.md`](../architecture-diagram.md) | Mermaid diagram (view) |
| [`../architecture-diagram.drawio`](../architecture-diagram.drawio) | draw.io editable diagram |
| [`../Internet-search.md`](../Internet-search.md) | Research + best-practice comparison |
| [`../reference/design.docx`](../reference/design.docx) | Official requirements + scenarios A–E |
