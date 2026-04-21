"""POR-158 A1.4 (Mistral day-2 trap) — ordinal dates must either extract
cleanly OR surface a low-confidence flag with source_text preserved.

Threat model: LLM reads "due on the 15th of May 2026", returns value
"2026-05-15" with confidence 0.95, and the UI shows "Due date: May 15, 2026"
with a green checkmark. If that pipeline exists, the reviewer has no way
to tell that the LLM dropped the ordinal suffix — they see a high-confidence
clean parse and trust it.

Our invariant: if a high-confidence extraction is reported, the source_text
must contain enough of the original token that a human auditor can spot
what was parsed. Specifically, for a date field with confidence >= 0.80:
    - value must be a parseable ISO date (YYYY-MM-DD)
    - source_text must contain a substring that evidences the parse (the
      day number, e.g. "15" or "15th", somewhere in the quoted text)

We don't hit the live Mistral API — this test pins the response-shape
contract that any classifier (current Mistral small, fallback, future swap)
must satisfy.
"""
from __future__ import annotations

import re

import pytest


ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── Acceptable extraction shapes ─────────────────────────────────────────────

ACCEPTABLE = [
    # (label, fields_payload)
    (
        "high_conf_with_ordinal_preserved",
        {
            "due_date": {
                "value": "2026-05-15",
                "confidence": 0.97,
                "source_text": "due on the 15th of May 2026",
            }
        },
    ),
    (
        "high_conf_with_bare_day_in_source",
        {
            "due_date": {
                "value": "2026-05-15",
                "confidence": 0.92,
                "source_text": "payment due by May 15, 2026",
            }
        },
    ),
    (
        "low_conf_ordinal_flagged",
        {
            "due_date": {
                "value": "15th May 2026",   # unparsed; low conf is fine
                "confidence": 0.42,
                "source_text": "due on the 15th of May 2026",
            }
        },
    ),
    (
        "no_source_text_low_conf_ok",
        {
            "due_date": {
                "value": None,
                "confidence": 0.31,
                "source_text": None,
            }
        },
    ),
]


# ── The failing shape — the trap we are trying to catch ──────────────────────

TRAP = {
    "due_date": {
        "value": "2026-05-15",   # cleanly parsed
        "confidence": 0.95,       # high
        "source_text": "",         # but no evidence of the original token
    }
}


def _check_date_audit_invariant(fields: dict) -> None:
    """Raise AssertionError if any date field violates the audit invariant.

    This mirrors the contract the UI + persona review will rely on: reviewer
    can always trace a high-confidence date back to its source token.
    """
    for name, field in fields.items():
        if not name.endswith("_date"):
            continue
        value = field.get("value")
        confidence = field.get("confidence")
        source_text = field.get("source_text") or ""

        if confidence is None or confidence < 0.80:
            # Low confidence is allowed — amber callout in the UI + manual verify
            continue

        # High confidence branch: require parseable ISO date + traceable source
        assert isinstance(value, str) and ISO_DATE.match(value), (
            f"{name}: high-confidence value must be ISO date, got {value!r}"
        )

        day_token = value.split("-")[-1].lstrip("0")  # "15" from "2026-05-15"
        assert day_token in source_text or f"{day_token}th" in source_text or \
               f"{day_token}st" in source_text or f"{day_token}nd" in source_text or \
               f"{day_token}rd" in source_text, (
            f"{name}: high-confidence date {value!r} has no day-token trace "
            f"in source_text={source_text!r}"
        )


@pytest.mark.parametrize("label,fields", ACCEPTABLE)
def test_acceptable_extraction_shapes_pass_invariant(label: str, fields: dict):
    _check_date_audit_invariant(fields)


def test_trap_shape_fails_invariant():
    """The trap payload MUST be rejected by the invariant check."""
    with pytest.raises(AssertionError, match="no day-token trace"):
        _check_date_audit_invariant(TRAP)


def test_invariant_tolerates_non_date_fields():
    """Non-date fields don't trip the check."""
    fields = {
        "call_amount": {"value": "$2,500,000", "confidence": 0.99, "source_text": ""},
        "fund_name": {"value": "Fund III", "confidence": 0.97, "source_text": "Fund III"},
    }
    # Must not raise
    _check_date_audit_invariant(fields)
