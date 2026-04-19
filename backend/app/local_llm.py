"""Local LLM client — vLLM OpenAI-compatible endpoint for self-hosted classification."""
import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

LOCAL_LLM_URL = os.environ.get("LOCAL_LLM_URL", "")  # e.g., http://localhost:8080/v1
LOCAL_LLM_MODEL = os.environ.get("LOCAL_LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")
LOCAL_LLM_TIMEOUT = 30


def is_configured() -> bool:
    return bool(LOCAL_LLM_URL)


def classify_with_local(text: str, filename: str, system_prompt: str) -> Optional[dict]:
    """Call local vLLM for classification. Returns parsed JSON or None on failure."""
    if not is_configured():
        return None

    url = f"{LOCAL_LLM_URL.rstrip('/')}/chat/completions"
    body = json.dumps({
        "model": LOCAL_LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Filename: {filename}\n\nDocument text:\n{text}"},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 1000,
        "temperature": 0.1,
    }).encode()

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        start = time.monotonic()
        with urllib.request.urlopen(req, timeout=LOCAL_LLM_TIMEOUT) as resp:
            data = json.loads(resp.read())
        duration_ms = int((time.monotonic() - start) * 1000)

        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        parsed["duration_ms"] = duration_ms
        parsed["provider_used"] = "local_llm"
        parsed["model_version"] = LOCAL_LLM_MODEL
        return parsed
    except Exception as e:
        logger.error("Local LLM failed: %s", e)
        return None
