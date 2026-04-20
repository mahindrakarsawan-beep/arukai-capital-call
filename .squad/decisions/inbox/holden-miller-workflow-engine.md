# Decision: Workflow Engine Selection

**Authors:** Holden (requirements) + Miller (validation)
**Date:** 2026-04-15
**Status:** RECOMMENDATION - awaiting Sawan approval
**Scope:** Replace custom state_machine.py, RBAC, and audit trail with third-party workflow engine

---

## Context

The Arukai Capital Call application has ~1,800 lines of custom workflow code spread across:

- `state_machine.py` (194 lines) - 6-state machine, role-transition matrix, business rules
- `audit_guard.py` (43 lines) - append-only audit enforcement
- `routers/packages.py` (900 lines) - claim/release/transition/attest endpoints with optimistic locking
- `routers/audit.py` (205 lines) - global audit ledger, CSV export, per-package trail
- `auth.py` (120 lines) - JWT auth + `require_role()` decorator
- `models.py` (328 lines) - Package state enum, AuditEvent, ReviewerNote, Approval models

This code works but has produced repeated bugs, slow iteration, and a confusing user experience. The directive is to replace it with a third-party engine that is reusable across multiple Arukai deployments.

---

## Evaluation Matrix

### 1. Temporal (temporal.io)

| Criterion | Score | Notes |
|---|---|---|
| Task assignment + roles + audit | PARTIAL | Workflow history = audit. No built-in task assignment or role-based human tasks. You'd still write custom task routing. |
| Cloud Run compatible | YES | Workers are stateless containers. Server needs persistent storage (PostgreSQL). Self-hosted Temporal Server is heavy (4+ services). |
| Learning curve | HIGH | Workflow-as-code paradigm is powerful but requires understanding activities, signals, queries, worker topology. Overkill for a 6-state approval flow. |
| Reusable across deployments | YES | Workflow definitions are versioned and portable. |
| Cost at small scale | FREE (OSS) | But operational cost is high - Temporal Server cluster is not trivial to run. Temporal Cloud starts at ~$200/mo. |

**Verdict: REJECT.** Temporal solves distributed orchestration problems we don't have. Our workflow is a simple human-task approval chain, not a saga across microservices. Temporal has no concept of "human task inbox" - we'd still build the task UI and role routing ourselves, defeating the purpose.

### 2. n8n (n8n.io)

| Criterion | Score | Notes |
|---|---|---|
| Task assignment + roles + audit | NO | n8n is an integration automation tool (Zapier alternative). No human task management, no role-based routing, no approval inbox. |
| Cloud Run compatible | YES | Single Docker container. |
| Learning curve | LOW | Visual workflow builder. |
| Reusable across deployments | PARTIAL | Workflows are exportable JSON but tightly coupled to trigger/action pairs. |
| Cost at small scale | FREE (OSS) | |

**Verdict: REJECT.** Wrong category entirely. n8n automates integrations between systems (send email when X happens). It does not manage human approval workflows with role-based task assignment.

### 3. Windmill (windmill.dev)

| Criterion | Score | Notes |
|---|---|---|
| Task assignment + roles + audit | PARTIAL | Has approval steps (suspend workflow, wait for human input). But no role-based task routing, no task inbox, no claim/release model. Approval is "someone clicks a link." |
| Cloud Run compatible | YES | Docker-based. Needs PostgreSQL. |
| Learning curve | MEDIUM | Python-native scripts + flows. Approval steps are simple. |
| Reusable across deployments | YES | Flows are YAML/JSON exportable. |
| Cost at small scale | FREE (OSS) | |

**Verdict: REJECT.** Windmill's approval steps are "pause workflow, send link, wait for click." This is not the same as "reviewer claims package, adds notes, routes to approver, approver attests with decision and note." We'd still build the entire task management layer.

### 4. Camunda (camunda.io)

| Criterion | Score | Notes |
|---|---|---|
| Task assignment + roles + audit | **YES - ALL THREE** | BPMN user tasks with assignee/candidate groups = task assignment + roles. Operate = full audit trail with before/after state. Tasklist = human task inbox UI out of the box. |
| Cloud Run compatible | YES | Zeebe broker + Operate + Tasklist run as Docker containers. Single-node dev mode available. Camunda 8 self-managed has a docker-compose. |
| Learning curve | MEDIUM-HIGH | BPMN modeling is a skill. But Camunda Modeler (desktop app) makes it visual. Python SDK (pyzeebe) is maintained. The BPMN is actually a strength - the workflow becomes a **visible, version-controlled diagram** rather than a transition matrix buried in code. |
| Reusable across deployments | **YES - STRONG** | BPMN process definitions are the reusable artifact. Deploy different .bpmn files for different Arukai products. Same engine, same task UI, different workflows. This is exactly what "commissioning core pattern" means. |
| Cost at small scale | FREE (OSS) | Camunda 8 Community Edition is Apache 2.0. Self-managed. Camunda Cloud (SaaS) has a free tier for dev. |

**Verdict: RECOMMEND.** Camunda is purpose-built for exactly this problem. Detailed analysis below.

### 5. Hatchet (hatchet.run)

| Criterion | Score | Notes |
|---|---|---|
| Task assignment + roles + audit | NO | Hatchet is a task queue / workflow engine for background jobs. No human task concept, no role routing, no approval flows. |
| Cloud Run compatible | YES | Docker-based. |
| Learning curve | LOW | Simple Python decorator-based API. |
| Reusable across deployments | YES | |
| Cost at small scale | FREE (OSS) | |

**Verdict: REJECT.** Same category as Temporal but simpler. Solves "run background tasks reliably" not "route human approval workflows."

### 6. Prefect (prefect.io)

| Criterion | Score | Notes |
|---|---|---|
| Task assignment + roles + audit | NO | Data pipeline orchestrator. No human tasks, no approval flows, no role management. |
| Cloud Run compatible | YES | |
| Learning curve | LOW | Python-native. |
| Reusable across deployments | YES | |
| Cost at small scale | FREE (OSS) | |

**Verdict: REJECT.** Wrong domain. Prefect orchestrates data pipelines (ETL). Not applicable to human approval workflows.

### 7. Simple approach (Linear/Notion API as task board)

| Criterion | Score | Notes |
|---|---|---|
| Task assignment + roles + audit | PARTIAL | Linear has assignees, statuses, and activity logs. But no RBAC enforcement - anyone can move any card. No state machine validation. No optimistic locking. You'd build enforcement in your API layer, which is... what we already have. |
| Cloud Run compatible | N/A | SaaS API. |
| Learning curve | LOW | REST API. |
| Reusable across deployments | NO | Tightly coupled to Linear's data model. No process versioning. |
| Cost at small scale | $8/user/mo | |

**Verdict: REJECT.** This just moves the UI to a third-party tool while keeping all the enforcement logic custom. We'd still need state_machine.py. We'd add API latency and a dependency on Linear's uptime for core workflow operations. Worse in every dimension.

---

## RECOMMENDATION: Camunda 8 (Self-Managed, Community Edition)

### Why Camunda wins decisively

Camunda is the only candidate that provides ALL THREE requirements out of the box:

1. **State machine** - BPMN process definitions replace `state_machine.py`. The 6-state workflow becomes a visual diagram with explicit transitions, role gates, and business rules modeled as gateway conditions. Version-controlled in git as `.bpmn` XML.

2. **Role-based task management** - BPMN User Tasks with `candidateGroups` replace custom RBAC. When a package reaches "intake_complete", Camunda creates a task visible only to the `reviewer` group. When routed for approval, a task appears in the `approver` group's inbox. Claim/release is built into Tasklist.

3. **Audit trail** - Camunda Operate provides a complete, append-only audit trail of every state transition, variable change, and task completion. Timestamps, actors, before/after state - all automatic. No custom `AuditEvent` model needed.

### What replaces what

| Current custom code | Camunda replacement |
|---|---|
| `state_machine.py` (194 lines) | `capital-call-workflow.bpmn` - visual BPMN diagram |
| `TRANSITION_PERMISSIONS` dict | BPMN User Tasks with `candidateGroups: ["reviewer"]`, `candidateGroups: ["approver"]` |
| `validate_transition()` | Zeebe engine enforces valid transitions automatically - impossible to skip states |
| `_write_audit()` calls (scattered across packages.py) | Automatic - Operate records every state change |
| `audit_guard.py` (43 lines) | DELETE - Operate's audit is immutable by design |
| `routers/audit.py` (205 lines) | Operate REST API replaces custom audit endpoints. CSV export via Operate's export API. |
| `require_role()` decorator for workflow actions | Zeebe task assignment handles role gating. `require_role()` stays for non-workflow endpoints (auth, upload). |
| Optimistic locking (`version` column, `WHERE version = X`) | Zeebe handles concurrency internally - one token per process instance, no concurrent state mutations possible |
| `Package.state` enum column | Process instance state lives in Zeebe. Package table keeps a denormalized `state` for query convenience, updated via Zeebe job workers. |
| `ReviewerNote` model | Stays as-is - notes are domain data, not workflow state. Worker attaches notes as process variables. |
| `Approval` model | Stays as-is - approval records are domain data. Attest worker creates the record AND completes the Zeebe user task atomically. |

### Integration architecture

```
Frontend (Next.js)
    |
    v
FastAPI Backend
    |-- /packages/upload  --> creates Package row + starts Zeebe process instance
    |-- /packages/{id}    --> reads Package + queries Zeebe for current state
    |-- /tasks            --> NEW: proxies Camunda Tasklist API (my tasks, claim, complete)
    |-- /audit/{id}       --> proxies Camunda Operate API
    |
    v
Zeebe Workers (Python, run inside FastAPI process or separate worker)
    |-- intake_worker     --> classifies document, completes service task
    |-- review_worker     --> handles note recording, routes to approval
    |-- attest_worker     --> records approval decision, completes user task
    |
    v
Zeebe Broker + Operate + Tasklist (Docker containers on Cloud Run or GKE)
```

### The BPMN process (capital-call-workflow.bpmn)

```
[Start] --> [Service Task: Classify Document]
                |
          [XOR Gateway: confidence >= 0.5?]
           /                    \
         YES                    NO
          |                      |
  [User Task:              [User Task:
   Review Package           Handle Exception
   candidateGroups:         candidateGroups:
   "reviewer"]              "admin"]
          |                      |
          |                 [XOR: resolved?]
          |                  /         \
          |                YES         NO (reject)
          |                 |            |
          |          [merge back]   [User Task: Attest
          |                         candidateGroups:
          |                         "approver"]
          |                              |
  [User Task:                    [End: Decision
   Route for Approval            Recorded]
   candidateGroups:
   "reviewer"]
          |
  [User Task: Attest
   candidateGroups:
   "approver"]
          |
  [XOR: approved?]
   /           \
 YES           NO
  |             |
[End:      [User Task:
Decision   Review Package  <-- return for revision loop
Recorded]  candidateGroups:
           "reviewer"]
```

### What gets deleted

| File | Action | Lines removed |
|---|---|---|
| `state_machine.py` | DELETE entirely | 194 |
| `audit_guard.py` | DELETE entirely | 43 |
| `routers/audit.py` | REWRITE to proxy Operate API | ~150 of 205 |
| `routers/packages.py` | SIMPLIFY: remove transition/claim/release/attest endpoints, replace with Zeebe task completion | ~400 of 900 |
| `models.py` | SIMPLIFY: remove `Package.state` enum (or keep as denormalized cache), remove `Package.version` (Zeebe handles concurrency), remove `AuditEvent` model | ~80 of 328 |
| `tests/test_state_machine.py` | DELETE - replaced by BPMN process tests | all |
| `tests/test_audit_append_only.py` | DELETE - Operate guarantees this | all |
| `tests/test_concurrency.py` | DELETE - Zeebe guarantees single-token execution | all |

**Estimated net deletion: ~900 lines of custom workflow code.**
**Estimated new code: ~200 lines (Zeebe workers + Tasklist proxy endpoints).**

### Cloud Run deployment

Camunda 8 self-managed runs as Docker containers:

- **Zeebe Broker** (workflow engine) - single node for small scale, needs persistent disk
- **Operate** (audit/monitoring UI) - stateless, reads from Elasticsearch
- **Tasklist** (human task UI) - stateless, reads from Elasticsearch
- **Elasticsearch** (event store) - needs persistent disk

**Cloud Run limitation:** Cloud Run is stateless. Zeebe and Elasticsearch need persistent storage.

**Recommended deployment:**
- **Option A (preferred):** Run Zeebe + Elasticsearch on a small GKE Autopilot cluster (e2-medium nodes). Run Operate + Tasklist on Cloud Run. FastAPI backend stays on Cloud Run.
- **Option B:** Run all Camunda components in a single Cloud Run service with Cloud SQL and mounted persistent volume. Less clean but simpler.
- **Option C:** Use Camunda SaaS (free tier for dev, ~$100/mo for production). Zero operational overhead. FastAPI connects to Camunda Cloud API.

For initial integration, **use Option C (Camunda SaaS)** to validate the architecture without operational overhead. Migrate to self-managed later if cost becomes a concern.

### Integration timeline

| Phase | Work | Duration |
|---|---|---|
| 1. BPMN modeling | Model the 6-state workflow in Camunda Modeler, deploy to Camunda SaaS | 2 days |
| 2. Zeebe workers | Write Python workers for classify, review-note, attest jobs | 3 days |
| 3. Tasklist proxy | Add `/tasks` endpoints that proxy Camunda Tasklist REST API to frontend | 2 days |
| 4. Audit proxy | Replace custom audit endpoints with Operate API proxy | 1 day |
| 5. Delete custom code | Remove state_machine.py, audit_guard.py, simplify packages.py | 1 day |
| 6. Frontend adaptation | Update frontend to use task-based UX (my tasks, claim from inbox, complete task) | 3 days |
| 7. Miller validation | Full test suite against Camunda-backed workflow | 2 days |

**Total: ~14 working days (3 sprints at current velocity)**

### Reusability across deployments

This is where Camunda pays for itself. The "commissioning core pattern" becomes:

1. Each Arukai product defines its own `.bpmn` file with product-specific states, roles, and business rules.
2. The Zeebe workers, Tasklist proxy, and audit proxy are shared infrastructure.
3. New products get workflow management by:
   - Designing a BPMN diagram (business analyst can do this)
   - Writing product-specific job workers (developer work)
   - Deploying the BPMN to the shared Camunda instance

No more copying and modifying `state_machine.py` for each product.

---

## AI Reviewer Role Change

### Current problem

The OpenAI + Mistral reviewers are configured as "visual critics" - they evaluate CSS aesthetics, color choices, and whether the UI looks "premium enough." This produces noisy, subjective feedback that doesn't catch functional workflow bugs.

### New role: Client Approver Simulation

Reassign AI reviewers to simulate actual workflow users:

**Prompt template for AI reviewers (replaces current visual critique prompt):**

```
You are a client user testing the Arukai Capital Call approval workflow.
Your role: {role} (one of: admin, reviewer, approver)

Walk through this workflow scenario:
1. Log in as {role}
2. Navigate to the package list
3. Attempt to {action} (e.g., "claim a package", "add a review note", "approve a document")
4. Report:
   - Could you find where to perform this action? (Y/N + explanation)
   - Did the action complete successfully? (Y/N + error message if any)
   - Was the state transition correct? (expected state vs actual state)
   - Was an audit event recorded? (Y/N)
   - Were you blocked from actions outside your role? (test one forbidden action)

Do NOT evaluate:
- Color choices, typography, or visual aesthetics
- Whether the design feels "premium" or "enterprise"
- CSS implementation details

DO evaluate:
- Can a user complete their workflow task without confusion?
- Are error messages clear when an action is forbidden?
- Does the audit trail accurately reflect what happened?
- Is the role-based access control working correctly?
```

**Specific test scenarios to run:**

1. **Reviewer happy path:** Login as reviewer -> claim package -> add note -> route for approval. Verify state is `routed_for_approval`.
2. **Approver happy path:** Login as approver -> see routed package -> attest approval with note. Verify state is `decision_recorded`.
3. **Role enforcement:** Login as reviewer -> attempt to attest. Verify 403 with clear message.
4. **Concurrent claim:** Two reviewer sessions -> both try to claim same package. Verify one gets 409.
5. **Exception handling:** Upload low-confidence document -> verify state is `exception_surfaced` -> login as admin -> resolve exception.
6. **Audit completeness:** Complete full workflow -> check audit trail has every transition with correct before/after states.

This directly validates whether the workflow engine integration is working, rather than whether the CSS looks nice.

---

## Risk assessment

| Risk | Mitigation |
|---|---|
| Camunda is too heavy for a small app | Start with Camunda SaaS (free tier). Only self-manage when scale demands it. |
| BPMN learning curve | Camunda Modeler is visual drag-and-drop. The 6-state workflow is simple enough to model in an afternoon. |
| pyzeebe SDK maturity | pyzeebe is maintained and used in production. Fallback: use Zeebe's gRPC API directly. |
| Vendor lock-in | BPMN is an ISO standard (ISO/IEC 19510). Process definitions are portable to other BPMN engines (e.g., Flowable, jBPM). |
| Elasticsearch operational cost | Camunda SaaS eliminates this. Self-managed: single-node ES is fine for our scale. |

---

## Decision requested

Sawan: approve or reject the recommendation to adopt Camunda 8 as the workflow engine for Arukai Capital Call, with the integration plan outlined above.

If approved, Holden will create the sprint tickets and Drummer will begin Phase 1 (BPMN modeling + Camunda SaaS setup).
