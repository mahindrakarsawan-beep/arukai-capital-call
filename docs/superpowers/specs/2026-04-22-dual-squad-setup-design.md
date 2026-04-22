# Dual-Squad Setup — Rocinante (capital-call) + Belter (portfolio-analyzer)

**Date:** 2026-04-22
**Status:** Design — ready for implementation plan
**Scope:** Configure two parallel 6-role squads with an opus/haiku/Codestral model mix, superpowers skills per role, shared global agent directory, TDD-mandatory for all devs.

---

## 1. Motivation

The user runs two projects that need to develop in parallel:

- **capital-call** (Arukai v1 Deployment 2) — active Phase 2B build, three open PRs, infra provisioning outstanding.
- **portfolio-analyzer** (Kuvera Portfolio checker, Deployment 1) — the reference implementation that seeded capital-call; still active.

Current global squad at `~/.claude/agents/` (bobbie, drummer, miller, alex, naomi) is:

1. Hardcoded to `/home/sawan/portfolio-analyzer` — breaks any other repo or the Windows host.
2. All-sonnet for implementers, opus for Miller — uniform, no cost tiering.
3. No Codestral/Mistral wiring at the squad layer (even though `scripts/mistral_coder.py` in capital-call already exists and the Linear history references Codestral-backed implementer work: POR-154/155).
4. Single team, single identity — can't parallelize two projects under distinct narratives.

This spec introduces two teams with distinct identities, a mixed opus/haiku/Codestral model plan, skills-per-role wiring, and a repo-agnostic global layout.

## 2. Team Structure

Both teams mirror the same 6-role shape: Lead + Test Gate + FE primary + BE primary + FE backup + BE backup.

| Role | Team 1 (Rocinante) | Team 2 (Belter) | Model | Runtime |
|------|---|---|---|---|
| Lead | Holden | Marco | opus | Main conversation (session-level, not a subagent) |
| Test gate | Miller | Ashford | opus | Claude subagent |
| FE primary | Bobbie | Michio | Codestral | `mistral_coder.py` sidecar |
| BE primary | Drummer | Filip | Codestral | `mistral_coder.py` sidecar |
| FE backup | Alex | Evita | haiku | Claude subagent |
| BE backup | Naomi | Diogo | haiku | Claude subagent |

**Team → project binding:**
- Rocinante → `arukai-capital-call`
- Belter → `portfolio-analyzer`
- Binding happens via each repo's `AGENTS.md`. The Claude subagents are globally defined and therefore callable from either repo, but the canonical pattern is team-in-repo.

## 3. Model Choices and Why

- **Opus for Lead + Test Gate** — these roles plan, decompose, synthesize evidence, and refuse bad handoffs. Reasoning depth matters more than throughput; cost is justified by low call volume.
- **Codestral for FE/BE primaries** — the bulk of implementation: structured code, repetitive patterns, test-first loops. Codestral is optimized for code and priced accordingly. Existing `mistral_coder.py` already enforces TDD with a `--tdd` flag.
- **Haiku for backups** — surge capacity and Copilot-fix work is bounded, fast, and needs cheap turnaround. Haiku is native-Claude so it can still invoke the Skill tool for `test-driven-development` + `verification-before-completion` + `receiving-code-review`.

## 4. Superpowers Skill Wiring

Claude-native subagents invoke skills via the Skill tool. Codestral-backed roles cannot — their skill content is **baked into the charter system prompt** so the behavior is still enforced.

| Role | Skills (invoked or baked) |
|------|---|
| **Holden / Marco** (lead, opus) | `brainstorming`, `writing-plans`, `executing-plans`, `dispatching-parallel-agents`, `using-git-worktrees`, `finishing-a-development-branch`, `verification-before-completion`, `requesting-code-review`, `systematic-debugging` — invoked natively |
| **Miller / Ashford** (test gate, opus) | `test-driven-development` (verify trail exists), `verification-before-completion` (every gate pass must cite evidence), `requesting-code-review` (test gate IS the review), `systematic-debugging` (when a test fails) — invoked natively |
| **Bobbie / Michio** (FE primary, Codestral) | `test-driven-development`, `verification-before-completion`, `receiving-code-review`, `systematic-debugging` — **baked into charter** |
| **Drummer / Filip** (BE primary, Codestral) | Same set as FE primary, plus backend-specific rules (reversible migrations, secrets hygiene, cost/token impact) — **baked into charter** |
| **Alex / Evita** (FE backup, haiku) | Same as FE primary — invoked natively via Skill tool |
| **Naomi / Diogo** (BE backup, haiku) | Same as BE primary — invoked natively via Skill tool |

**Why baking vs invoking matters:** Codestral has no Skill tool access. If we only referenced skill *names* in the charter, Codestral would ignore them. Inlining the rules (TDD workflow order, verification checklist, receiving-review protocol) turns the skills into enforceable system-prompt rules. The existing 12-rule pre-Miller checklist in `bobbie.md`/`drummer.md` already covers most of `verification-before-completion` + `test-driven-development` — the migration preserves those checklists and adds `receiving-code-review` discipline.

## 5. File Layout

```
~/.claude/agents/                           Claude subagents (global, repo-agnostic)
  miller.md        opus, Roci test gate
  alex.md          haiku, Roci FE backup
  naomi.md         haiku, Roci BE backup
  ashford.md       opus, Belter test gate
  evita.md         haiku, Belter FE backup
  diogo.md         haiku, Belter BE backup

~/.claude/squad/codestral/                  Charters fed to mistral_coder.py as system prompts
  bobbie.md        Roci FE primary
  drummer.md       Roci BE primary
  michio.md        Belter FE primary
  filip.md         Belter BE primary

~/.claude/squad/scripts/mistral_coder.py    Global copy (copied from capital-call)

arukai-capital-call/AGENTS.md               NEW — Rocinante team identity (Holden)
portfolio-analyzer/AGENTS.md                REWRITE — Belter team identity (Marco)
```

The existing `~/.claude/agents/bobbie.md` and `~/.claude/agents/drummer.md` are **removed** from that directory (not left as Claude subagents) and replaced by the Codestral charter versions under `~/.claude/squad/codestral/`.

## 6. Belter Voice

Belter roles (Marco, Ashford, Michio, Filip, Evita, Diogo) carry a Lang Belta register in their charters — tone, not cosplay. Used sparingly so the rules stay executable.

**Vocabulary leaned on:** *beltalowda* (us), *inyalowda* (Inners, the outside), *mowteng* (crew / movement), *kopeng* (friend), *bosmang* (boss), *sasa ke* (do you know), *welwala* (traitor), *to dui* (to work), *pochuye mi* (hear me), *tumang* (true), *gut* (good), *alles gut* (all good), *imim* (them).

**Tone:** crew-loyal, Inner-wary, pragmatic, terse, evidence-first. No performative jargon — the charter must still be executable by Codestral.

**Sample Ashford charter voice (excerpt):**

> You are Ashford, the test gate for the Belter mowteng. Sasa ke: mi job is no to write code. Mi job is to bounce work when the evidence no there. Inyalowda ship pretty abstractions; beltalowda ship evidence. Failing test first, du sasa ke, or the PR no opens. Tumang.

Roci roles keep the existing operational voice — precise, low-drama, no Lang Belta.

## 7. Invocation Patterns

**Claude subagents** (all six: miller, alex, naomi, ashford, evita, diogo):

```
Agent(subagent_type="miller", prompt="Validate POR-158 PR #7 against AC…")
Agent(subagent_type="ashford", prompt="Gate POR-83 Defang cutover …")
```

**Codestral sidecar** — charter is prepended to the task so the Codestral system prompt includes role identity + baked skill rules:

```bash
CHARTER=$(cat ~/.claude/squad/codestral/bobbie.md)
python3 ~/.claude/squad/scripts/mistral_coder.py --tdd \
  --task "$CHARTER

TASK: implement the flag-field endpoint from POR-160
  - Route: POST /packages/{pkg_id}/flag-field
  - Audit event kind: field_review_requested
  - Follow repo's existing router pattern" \
  --files backend/app/routers/packages.py backend/app/models.py \
  --output /tmp/bobbie_output.md
```

The current `mistral_coder.py` has no `--system-prompt-file` flag, so the charter lands in the **user message** alongside the task (not in the system prompt). Codestral still reads it and adheres to the role — but for stricter role enforcement the implementation plan may add a `--system-prompt-file <path>` flag that overrides or appends to the built-in `--tdd` system prompt. Decision deferred to the plan; either path meets the success criteria.

**Handoff protocol unchanged:**
- Bobbie/Drummer/Michio/Filip output → Holden/Marco applies via Edit/Write → Miller/Ashford gates → Holden/Marco opens the PR.
- Alex/Evita/Naomi/Diogo work on Copilot-fix branches directly; hand to Miller/Ashford before pushing.

## 8. Path Portability

Every charter must work regardless of the host OS or repo path. Concretely:

- Replace every `/home/sawan/portfolio-analyzer` with phrasing like *"the current project repo root"* or *"wherever this session is running"*.
- Remove OS-specific path examples; use tool-agnostic language (pytest, npm, etc.).
- Each repo's `AGENTS.md` names the team and sets repo-specific conventions (test commands, deploy targets, Linear team).

## 9. Per-Repo AGENTS.md Content

**`arukai-capital-call/AGENTS.md`** (new):
- "You are Holden, leading the Rocinante squad in the Arukai Capital Call project."
- Team roster + model table.
- Linear team: Portfolio-checker, project: Arukai Commissioning Core.
- Cloud Run + Codestral API key env requirements.
- Reference to `.squad/` decisions and scorecards.

**`portfolio-analyzer/AGENTS.md`** (rewrite of existing):
- "You are Marco, leading the Belter mowteng in the Kuvera Portfolio checker project."
- Team roster + model table.
- Preserve all existing operational content (Linear gate, testing pyramid, PR ↔ Linear lifecycle, Cloud Run deploy contract, skill adoption policy) — just swap the identity header.
- Belter tone only in role framing, not in operational rules.

## 10. TDD Is Mandatory (All Devs, Both Teams)

Every dev role — Bobbie, Drummer, Michio, Filip, Alex, Evita, Naomi, Diogo — must follow TDD:

1. Failing test committed before implementation.
2. Verifiable TDD trail via `git log --oneline`.
3. Miller/Ashford bounces any handoff that lacks the trail — no "simple change" exemption.

This applies regardless of model: Codestral's `--tdd` flag enforces it at the system-prompt level; Claude subagents invoke `test-driven-development` skill; Miller/Ashford verify the trail exists on every gate pass.

## 11. Migration Steps (preview for implementation plan)

1. Write design doc (this file).
2. Copy `arukai-capital-call/scripts/mistral_coder.py` → `~/.claude/squad/scripts/mistral_coder.py`.
3. Update `~/.claude/agents/miller.md` — strip hardcoded path, clarify skill invocations, keep pre-Miller 12-rule grading.
4. Update `~/.claude/agents/alex.md` — model `sonnet` → `haiku`, strip path.
5. Update `~/.claude/agents/naomi.md` — model `sonnet` → `haiku`, strip path.
6. Delete `~/.claude/agents/bobbie.md`, `~/.claude/agents/drummer.md` (they become Codestral charters, not Claude subagents).
7. Create `~/.claude/squad/codestral/bobbie.md` and `drummer.md` — role charters with baked TDD + verification + receiving-review rules, plus Roci operational voice.
8. Create `~/.claude/agents/ashford.md` (opus), `evita.md` (haiku), `diogo.md` (haiku) — Belter subagent charters with Lang Belta tone.
9. Create `~/.claude/squad/codestral/michio.md`, `filip.md` — Belter Codestral charters with Lang Belta tone.
10. Create `arukai-capital-call/AGENTS.md` (Holden identity).
11. Rewrite `portfolio-analyzer/AGENTS.md` (Marco identity, existing content preserved).
12. Commit each team's AGENTS.md inside its repo. Global files are uncommitted (they live in `~/.claude/`).
13. Write the implementation plan (writing-plans skill) and execute.

## 12. Success Criteria

- `Agent(subagent_type="miller")` works from capital-call; `Agent(subagent_type="ashford")` works from portfolio-analyzer.
- `python3 ~/.claude/squad/scripts/mistral_coder.py --tdd --task "<charter>\n\nTASK: …" --files …` returns valid Codestral output with failing tests first, then implementation.
- No charter contains `/home/sawan/portfolio-analyzer`.
- Each repo's `AGENTS.md` correctly names its team's lead and roster.
- TDD trail is verifiable via `git log --oneline` for any handoff from any dev role.
- Running work in parallel: capital-call session uses Roci names; portfolio-analyzer session uses Belter names; both can run simultaneously without cross-talk.

## 13. Open Questions (resolved during brainstorming, noted here for the plan)

- **Q: Codex/Mistral CLI install?** → Deferred. Use existing `scripts/mistral_coder.py` (copied to global location). CLI upgrade is a future spec.
- **Q: Superpowers for Codestral roles?** → Baked into charter system prompts (Codestral has no Skill tool).
- **Q: Team-to-project binding?** → Roci → capital-call, Belter → portfolio-analyzer.
- **Q: Belter names?** → Marco, Ashford, Michio, Filip, Evita, Diogo (approved).

## 14. Out of Scope

- Multi-provider orchestrator / MCP connector for Mistral.
- Shared agent runtime across both teams within the same session (one lead per session).
- Porting `mistral_coder.py` to other languages/runtimes.
- Monitoring/observability for squad spend — tracked separately.
- Authentik / SSO / credential rotation for squad API keys.
