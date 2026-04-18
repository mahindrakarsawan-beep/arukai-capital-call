#!/usr/bin/env python3
"""
Arukai AI Provider Benchmark

Empirical comparison of OpenAI vs Mistral vs Claude Haiku for document
classification + field extraction. Same document, same prompt, same schema.

Measures: latency, token usage, cost, classification accuracy, field extraction
quality, reasoning depth.

Usage:
    python3 scripts/ai_benchmark.py \
        --anthropic-key $ANTHROPIC_API_KEY \
        --openai-key $OPENAI_API_KEY \
        --mistral-key $MISTRAL_API_KEY \
        --pdf-path /home/sawan/test-capital-call.pdf \
        --runs 3
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen


@dataclass
class BenchmarkResult:
    provider: str
    model: str
    run: int
    latency_ms: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    doc_type: str
    confidence: float
    key_indicators: list[str]
    fields_extracted: dict  # {field_name: {value, confidence}}
    reasoning: str
    raw_response: str
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Pricing (per 1M tokens, as of 2026-04)
# ---------------------------------------------------------------------------
PRICING = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "mistral-small-latest": {"input": 0.10, "output": 0.30},
}


def _calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p = PRICING.get(model, {"input": 1.0, "output": 3.0})
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


# ---------------------------------------------------------------------------
# Shared prompt (identical for all providers)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a financial document classifier for a capital call management system.

Given the text of a document, you must:
1. Classify it as one of: capital_call_notice, subscription_agreement, side_letter, k1, wire_instructions, other
2. Provide a confidence score (0.0-1.0)
3. List key indicators that led to your classification
4. Explain your reasoning in 2-3 sentences
5. Extract these fields with per-field confidence:
   - fund_name (string)
   - call_number (string)
   - amount_due (string)
   - currency (string)
   - due_date (string)
   - recipient_entity (string)
   - wire_instructions_present (boolean)
   - notice_date (string)

Return your response as JSON with this exact structure:
{
    "document_type": "capital_call_notice",
    "confidence": 0.99,
    "key_indicators": ["phrase1", "phrase2"],
    "reasoning": "I classified this as... because...",
    "extracted_fields": {
        "fund_name": {"value": "...", "confidence": 0.99},
        "call_number": {"value": "...", "confidence": 0.95},
        ...
    }
}

Return ONLY valid JSON. No markdown, no explanation outside the JSON."""


def extract_pdf_text(pdf_path: str) -> str:
    """Extract text from PDF."""
    try:
        from pypdf import PdfReader
        import io
        with open(pdf_path, "rb") as f:
            reader = PdfReader(io.BytesIO(f.read()))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        with open(pdf_path, "r", errors="ignore") as f:
            return f.read()


# ---------------------------------------------------------------------------
# Provider-specific API calls
# ---------------------------------------------------------------------------

def _call_anthropic(api_key: str, text: str) -> dict:
    """Call Claude Haiku."""
    model = "claude-haiku-4-5-20251001"
    body = json.dumps({
        "model": model,
        "max_tokens": 1000,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": f"Classify and extract fields from this document:\n\n{text}"}]
    }).encode()

    req = Request("https://api.anthropic.com/v1/messages", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("x-api-key", api_key)
    req.add_header("anthropic-version", "2023-06-01")

    start = time.time()
    resp = urlopen(req, timeout=30)
    latency = int((time.time() - start) * 1000)

    result = json.loads(resp.read().decode())
    content = result["content"][0]["text"]
    usage = result.get("usage", {})

    return {
        "model": model,
        "latency_ms": latency,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "content": content,
    }


def _call_openai(api_key: str, text: str) -> dict:
    """Call GPT-4o-mini."""
    model = "gpt-4o-mini"
    body = json.dumps({
        "model": model,
        "max_tokens": 1000,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Classify and extract fields from this document:\n\n{text}"}
        ]
    }).encode()

    req = Request("https://api.openai.com/v1/chat/completions", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")

    start = time.time()
    resp = urlopen(req, timeout=30)
    latency = int((time.time() - start) * 1000)

    result = json.loads(resp.read().decode())
    content = result["choices"][0]["message"]["content"]
    usage = result.get("usage", {})

    return {
        "model": model,
        "latency_ms": latency,
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
        "content": content,
    }


def _call_mistral(api_key: str, text: str) -> dict:
    """Call Mistral Small."""
    model = "mistral-small-latest"
    body = json.dumps({
        "model": model,
        "max_tokens": 1000,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Classify and extract fields from this document:\n\n{text}"}
        ]
    }).encode()

    req = Request("https://api.mistral.ai/v1/chat/completions", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")

    start = time.time()
    resp = urlopen(req, timeout=30)
    latency = int((time.time() - start) * 1000)

    result = json.loads(resp.read().decode())
    content = result["choices"][0]["message"]["content"]
    usage = result.get("usage", {})

    return {
        "model": model,
        "latency_ms": latency,
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
        "content": content,
    }


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

GROUND_TRUTH = {
    "document_type": "capital_call_notice",
    "fund_name": "Meridian Capital Partners III, L.P.",
    "call_number": "14",
    "amount_due": "USD 2,500,000",
    "currency": "USD",
    "due_date": "2026-05-15",
    "recipient_entity": "Meridian Family Office",
    "wire_instructions_present": True,
}

EXPECTED_FIELDS = ["fund_name", "call_number", "amount_due", "currency",
                    "due_date", "recipient_entity", "wire_instructions_present", "notice_date"]


def _parse_response(content: str) -> dict:
    """Parse JSON from LLM response, handling markdown fences."""
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        if content.startswith("json"):
            content = content[4:].strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


def _score_accuracy(parsed: dict) -> dict:
    """Score classification + extraction accuracy against ground truth."""
    scores = {}

    # Classification accuracy
    scores["classification_correct"] = parsed.get("document_type") == GROUND_TRUTH["document_type"]
    scores["confidence"] = parsed.get("confidence", 0.0)

    # Field extraction accuracy
    fields = parsed.get("extracted_fields", {})
    correct_fields = 0
    total_fields = len(EXPECTED_FIELDS)
    field_details = {}

    for fname in EXPECTED_FIELDS:
        field_data = fields.get(fname, {})
        value = field_data.get("value") if isinstance(field_data, dict) else field_data
        gt = GROUND_TRUTH.get(fname)

        if gt is not None:
            if isinstance(gt, bool):
                match = value == gt or str(value).lower() in ("true", "yes", "1")
            else:
                match = gt.lower() in str(value).lower() if value else False
        else:
            match = value is not None  # notice_date — any non-null is acceptable

        if match:
            correct_fields += 1
        field_details[fname] = {"value": value, "match": match,
                                 "confidence": field_data.get("confidence", 0) if isinstance(field_data, dict) else 0}

    scores["fields_correct"] = correct_fields
    scores["fields_total"] = total_fields
    scores["fields_accuracy"] = correct_fields / total_fields if total_fields > 0 else 0
    scores["field_details"] = field_details
    scores["reasoning_length"] = len(parsed.get("reasoning", ""))
    scores["key_indicators_count"] = len(parsed.get("key_indicators", []))

    return scores


def run_benchmark(pdf_path: str, anthropic_key: str, openai_key: str,
                   mistral_key: str, runs: int = 3):
    """Run the full benchmark."""

    text = extract_pdf_text(pdf_path)
    print(f"Document: {pdf_path} ({len(text)} chars)")
    print(f"Runs per provider: {runs}")
    print(f"Ground truth: {GROUND_TRUTH['document_type']}, {GROUND_TRUTH['fund_name']}")

    providers = []
    if anthropic_key:
        providers.append(("Anthropic Claude Haiku", _call_anthropic, anthropic_key))
    if openai_key:
        providers.append(("OpenAI GPT-4o-mini", _call_openai, openai_key))
    if mistral_key:
        providers.append(("Mistral Small", _call_mistral, mistral_key))

    all_results = {}

    for provider_name, call_fn, key in providers:
        print(f"\n{'='*50}")
        print(f"  {provider_name}")
        print(f"{'='*50}")

        results = []
        for run_num in range(1, runs + 1):
            print(f"  Run {run_num}/{runs}...", end=" ", flush=True)
            try:
                raw = call_fn(key, text)
                parsed = _parse_response(raw["content"])
                scores = _score_accuracy(parsed)

                cost = _calc_cost(raw["model"], raw["input_tokens"], raw["output_tokens"])

                print(f"{raw['latency_ms']}ms, ${cost:.6f}, "
                      f"class={'✓' if scores['classification_correct'] else '✗'}, "
                      f"fields={scores['fields_correct']}/{scores['fields_total']}")

                results.append({
                    "run": run_num,
                    "model": raw["model"],
                    "latency_ms": raw["latency_ms"],
                    "input_tokens": raw["input_tokens"],
                    "output_tokens": raw["output_tokens"],
                    "cost_usd": cost,
                    "classification_correct": scores["classification_correct"],
                    "confidence": scores["confidence"],
                    "fields_correct": scores["fields_correct"],
                    "fields_total": scores["fields_total"],
                    "fields_accuracy": scores["fields_accuracy"],
                    "reasoning_length": scores["reasoning_length"],
                    "key_indicators_count": scores["key_indicators_count"],
                    "field_details": scores["field_details"],
                    "reasoning": parsed.get("reasoning", ""),
                })
            except Exception as e:
                print(f"ERROR: {e}")
                results.append({"run": run_num, "error": str(e)})

            time.sleep(0.5)  # rate limit courtesy

        all_results[provider_name] = results

    # Print summary
    print("\n\n" + "=" * 80)
    print("BENCHMARK SUMMARY")
    print("=" * 80)

    print(f"\n{'Provider':<25} {'Model':<28} {'Avg Latency':<14} {'Avg Cost':<12} "
          f"{'Class Acc':<12} {'Field Acc':<12} {'Reasoning':<12}")
    print("-" * 115)

    summary_rows = []
    for provider_name, results in all_results.items():
        valid = [r for r in results if "error" not in r]
        if not valid:
            print(f"{provider_name:<25} ALL RUNS FAILED")
            continue

        model = valid[0]["model"]
        avg_latency = sum(r["latency_ms"] for r in valid) / len(valid)
        avg_cost = sum(r["cost_usd"] for r in valid) / len(valid)
        class_acc = sum(1 for r in valid if r["classification_correct"]) / len(valid) * 100
        field_acc = sum(r["fields_accuracy"] for r in valid) / len(valid) * 100
        avg_reasoning = sum(r["reasoning_length"] for r in valid) / len(valid)

        print(f"{provider_name:<25} {model:<28} {avg_latency:>8.0f}ms    "
              f"${avg_cost:>8.6f}  {class_acc:>8.0f}%     {field_acc:>8.1f}%     "
              f"{avg_reasoning:>6.0f} chars")

        summary_rows.append({
            "provider": provider_name,
            "model": model,
            "avg_latency_ms": avg_latency,
            "avg_cost_usd": avg_cost,
            "classification_accuracy": class_acc,
            "field_accuracy": field_acc,
            "avg_reasoning_chars": avg_reasoning,
            "runs": len(valid),
        })

    # Cost projection
    print("\n\n--- COST PROJECTION (1000 documents/month) ---")
    for row in summary_rows:
        monthly = row["avg_cost_usd"] * 1000
        print(f"  {row['provider']:<25} ${monthly:>8.2f}/month")

    # Reasoning quality sample
    print("\n\n--- REASONING QUALITY SAMPLE (last run each) ---")
    for provider_name, results in all_results.items():
        valid = [r for r in results if "error" not in r]
        if valid:
            last = valid[-1]
            print(f"\n  {provider_name}:")
            print(f"    \"{last['reasoning'][:300]}\"")

    # Field extraction detail
    print("\n\n--- FIELD EXTRACTION DETAIL (last run) ---")
    for provider_name, results in all_results.items():
        valid = [r for r in results if "error" not in r]
        if valid:
            last = valid[-1]
            print(f"\n  {provider_name}:")
            for fname, detail in last.get("field_details", {}).items():
                match = "✓" if detail["match"] else "✗"
                print(f"    {match} {fname}: {detail['value']} (conf: {detail['confidence']})")

    # Save full results
    output_path = Path(pdf_path).parent / "ai_benchmark_results.json"
    with open(output_path, "w") as f:
        json.dump({"summary": summary_rows, "detailed": {k: v for k, v in all_results.items()}}, f, indent=2, default=str)
    print(f"\n\nFull results saved to: {output_path}")

    print("\n" + "=" * 80)
    return summary_rows


def main():
    parser = argparse.ArgumentParser(description="Arukai AI Provider Benchmark")
    parser.add_argument("--anthropic-key", default=os.environ.get("ANTHROPIC_API_KEY", ""))
    parser.add_argument("--openai-key", default=os.environ.get("OPENAI_API_KEY", ""))
    parser.add_argument("--mistral-key", default=os.environ.get("MISTRAL_API_KEY", ""))
    parser.add_argument("--pdf-path", default="/home/sawan/test-capital-call.pdf")
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    run_benchmark(args.pdf_path, args.anthropic_key, args.openai_key,
                  args.mistral_key, args.runs)


if __name__ == "__main__":
    main()
