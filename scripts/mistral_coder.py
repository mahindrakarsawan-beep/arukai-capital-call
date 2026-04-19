#!/usr/bin/env python3
"""
Mistral Codestral Coder — squad tool for Drummer/Alex/Naomi

Sends coding tasks to Codestral, returns code. Human reviews before applying.

Usage:
    # Generate code from a task description
    python3 scripts/mistral_coder.py --task "Write a rate limiting middleware for FastAPI" \
        --files backend/app/main.py backend/app/routers/packages.py \
        --output /tmp/codestral_output.py

    # With context files (reads first 200 lines of each)
    python3 scripts/mistral_coder.py --task "Add AES-256 encryption to extracted_fields" \
        --files backend/app/models.py backend/app/routers/packages.py

    # Review mode: just show the diff, don't write
    python3 scripts/mistral_coder.py --task "Fix the JWT token revocation" \
        --files backend/app/auth.py --review-only
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen


CODESTRAL_URL = "https://codestral.mistral.ai/v1/chat/completions"
CODESTRAL_MODEL = "codestral-latest"
MAX_CONTEXT_LINES = 200


def read_file_context(file_path: str, max_lines: int = MAX_CONTEXT_LINES) -> str:
    """Read a file, truncated to max_lines."""
    p = Path(file_path)
    if not p.exists():
        return f"# FILE NOT FOUND: {file_path}"
    lines = p.read_text().splitlines()
    content = "\n".join(lines[:max_lines])
    if len(lines) > max_lines:
        content += f"\n\n# ... truncated ({len(lines) - max_lines} more lines)"
    return content


def call_codestral(api_key: str, task: str, file_contexts: dict, max_tokens: int = 4000, args=None) -> dict:
    """Send a coding task to Codestral."""

    context_block = ""
    for fname, content in file_contexts.items():
        context_block += f"\n--- {fname} ---\n{content}\n"

    tdd_mode = args.tdd if hasattr(args, 'tdd') else False

    if tdd_mode:
        system = """You are a senior Python/TypeScript developer practicing strict TDD.

WORKFLOW (you MUST follow this order):
1. FIRST write the failing test(s) — pytest style, clear assertions, edge cases covered
2. THEN write the minimal implementation to make those tests pass
3. Show tests BEFORE implementation in your output

RULES:
- Tests go in tests/ directory matching the module path
- Use existing test patterns from the codebase context
- Each test function tests ONE behavior
- Include edge cases: null/None inputs, empty strings, invalid types, boundary values
- Mock external dependencies (API calls, DB) — never hit real services
- No unnecessary comments
- Include all imports needed
- Mark clearly: TESTS FIRST, then IMPLEMENTATION"""

        user = f"""TASK: {task}

EXISTING CODE CONTEXT:
{context_block}

Follow TDD strictly. Output in this order:

1. FAILING TESTS:
FILE: tests/<test_file>.py
```python
<test code>
```

2. IMPLEMENTATION (makes tests pass):
FILE: <path>
```python
<code>
```"""
    else:
        system = """You are a senior Python/TypeScript developer working on the Arukai Capital Call project.
You write clean, production-quality code. Follow these rules:
- No unnecessary comments (code should be self-documenting)
- Use existing patterns from the codebase context provided
- Return ONLY the code that needs to change (not entire files)
- Clearly mark which file each change belongs to
- Include any new imports needed
- If creating a new file, show the complete file content"""

        user = f"""TASK: {task}

EXISTING CODE CONTEXT:
{context_block}

Write the code changes needed. For each file, show:
FILE: <path>
```python
<code>
```"""

    body = json.dumps({
        "model": CODESTRAL_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.1
    }).encode()

    req = Request(CODESTRAL_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")

    start = time.time()
    resp = urlopen(req, timeout=120)
    latency = time.time() - start

    result = json.loads(resp.read().decode())
    usage = result.get("usage", {})

    return {
        "content": result["choices"][0]["message"]["content"],
        "latency_s": round(latency, 1),
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
        "model": CODESTRAL_MODEL,
    }


def main():
    parser = argparse.ArgumentParser(description="Mistral Codestral Coder")
    parser.add_argument("--task", required=True, help="Coding task description")
    parser.add_argument("--files", nargs="*", default=[], help="Context files to read")
    parser.add_argument("--output", help="Write output to file (default: stdout)")
    parser.add_argument("--review-only", action="store_true", help="Show output, don't write")
    parser.add_argument("--tdd", action="store_true", help="TDD mode: generate failing tests first, then implementation")
    parser.add_argument("--key", default=os.environ.get("CODESTRAL_API_KEY", ""),
                        help="Codestral API key")
    parser.add_argument("--max-tokens", type=int, default=4000)
    args = parser.parse_args()

    if not args.key:
        print("ERROR: --key or CODESTRAL_API_KEY required")
        sys.exit(1)

    # Read context files
    file_contexts = {}
    for f in args.files:
        file_contexts[f] = read_file_context(f)
        print(f"  Read: {f} ({len(file_contexts[f].splitlines())} lines)")

    print(f"\n  Task: {args.task}")
    print(f"  Model: {CODESTRAL_MODEL}")
    print(f"  Context: {len(file_contexts)} files")
    print(f"  Sending to Codestral...\n")

    result = call_codestral(args.key, args.task, file_contexts, args.max_tokens, args)

    print(f"  Latency: {result['latency_s']}s")
    print(f"  Tokens: {result['input_tokens']} in / {result['output_tokens']} out")
    print(f"\n{'='*80}")
    print(result["content"])
    print(f"{'='*80}\n")

    if args.output and not args.review_only:
        Path(args.output).write_text(result["content"])
        print(f"  Output saved to: {args.output}")


if __name__ == "__main__":
    main()
