# Squad Lessons Learned — AI Provider Selection Must Be Empirical

**Date:** 2026-04-18
**Severity:** Process failure — cost and quality impact
**Filed by:** Holden (on Sawan's directive)

---

## What happened

The squad chose Claude Haiku for D2's document classification pipeline **without benchmarking alternatives.** The choice was made by default because the squad itself runs on Claude. No one questioned it. No one ran a comparison.

Sawan caught this and asked for an empirical benchmark before finishing the work.

## Benchmark results (3 runs each, same document, same prompt)

| Provider | Model | Field Accuracy | Avg Latency | Cost/doc | Monthly (1K) |
|----------|-------|---------------|-------------|----------|-------------|
| Anthropic | claude-haiku-4-5-20251001 | **75%** (6/8) | 3,321ms | $0.00203 | $2.03 |
| OpenAI | gpt-4o-mini | **100%** (8/8) | 6,156ms | $0.00022 | $0.22 |
| Mistral | mistral-small-latest | **75%** (6/8) | 2,091ms | $0.00013 | $0.13 |

## What went wrong

1. **Model affinity bias.** The squad is powered by Claude. Drummer wrote `HAIKU_MODEL = "claude-haiku-4-5-20251001"` in `classify.py` without considering alternatives. Nobody in the review chain (Bobbie, Miller, Holden, Naomi, Alex) questioned the choice. It felt natural because we're Claude agents.

2. **No benchmark step in the process.** The 14-rule Copilot KPI checklist, the Miller gate, the Holden review — none of them include "did you benchmark the AI provider?" It's not in any charter, spec, or acceptance criteria.

3. **Cost blindness.** $2.03/month at 1K docs sounds cheap. But it's **10x** what GPT-4o-mini costs for **better accuracy.** At scale (100K docs/month), that's $203 vs $22. The squad optimized tokens elsewhere (Haiku for classification is "cheap") without comparing against actual alternatives.

## The fix

### New rule for all squad members

**Rule 16 — AI Provider Benchmark**

Before any ticket ships code that calls an AI provider API:
1. Run `scripts/ai_benchmark.py` (or equivalent) with the actual prompt against at least 3 providers
2. Post the benchmark results as a Linear comment on the ticket
3. The provider choice must cite the benchmark, not default to any provider
4. Holden signs off on the AI provider selection

### For D2 specifically

Based on the benchmark:
- **Switch production pipeline from Haiku to GPT-4o-mini** — 100% field accuracy, 10x cheaper
- **Keep Mistral as a fallback** — fastest, cheapest, adequate for classification-only (no field extraction)
- **Haiku is dropped from production** — it was never the right choice for this task

### For the commissioning core

Update the following artifacts:
- `pattern-extraction.md` — add P21: "AI provider benchmark before selection"
- `blueprint-template.md` — add "AI provider benchmark" as a milestone gate
- `intake-schema.json` — change `ai_requirements.model_preferences` default guidance to "benchmark-pending, not a named model"
- `feasibility-model.md` — D2 dimension scoring should note that provider choice is validated empirically, not assumed

### For squad charters

Every squad member's charter should include awareness:
- **Drummer/Naomi:** Never hard-code a provider without benchmark data
- **Miller:** Add "AI provider benchmarked?" to the pre-PR checklist
- **Holden:** Review AI provider selection as an architecture decision, not a default
- **Bobbie/Alex:** Flag if the backend uses a provider without benchmark evidence

## How this fits the commissioning core story

This is actually a **positive commissioning core finding** for investors:
- The framework caught a cost/quality misallocation within the same deployment
- The benchmark script (`ai_benchmark.py`) is now a reusable commissioning core artifact
- Future deployments will select providers empirically, not by affinity
- This prevents a silent cost problem from compounding across D3, D4, D5+

## Bottom line

The squad defaulted to its own provider because it felt natural. That's exactly the kind of bias a commissioning framework should catch. Now it does.

---

*Every squad member should read this. This is not a blame exercise — it's a process gap that affected every prior decision about AI selection. Rule 16 closes it.*
