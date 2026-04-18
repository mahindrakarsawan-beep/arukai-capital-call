"""TDD: Provider fallback chain tests (POR-151).

Covers: Mistral fails → OpenAI fallback → heuristic fallback.
"""
import pytest
from unittest.mock import patch, call


CAPITAL_CALL_FIELDS = [
    "fund_name",
    "call_number",
    "amount_due",
    "currency",
    "due_date",
    "recipient_entity",
    "wire_instructions_present",
    "notice_date",
]


def _ok_clf(doc_type="capital_call_notice", confidence=0.90):
    return {
        "document_type": doc_type,
        "confidence": confidence,
        "key_indicators": ["capital call"],
    }


def _ok_extract():
    return {
        "fund_name": {"value": "Test Fund", "confidence": 0.9, "source_text": "Test Fund"},
        "call_number": {"value": "Q1", "confidence": 0.8, "source_text": "Q1"},
        "amount_due": {"value": "500000", "confidence": 0.85, "source_text": "$500,000"},
        "currency": {"value": "USD", "confidence": 1.0, "source_text": "USD"},
        "due_date": {"value": "2026-05-01", "confidence": 0.9, "source_text": "May 1, 2026"},
        "recipient_entity": {"value": "LP Inc", "confidence": 0.8, "source_text": "LP Inc"},
        "wire_instructions_present": {"value": False, "confidence": 0.7, "source_text": None},
        "notice_date": {"value": "2026-04-01", "confidence": 0.9, "source_text": "April 1, 2026"},
    }


# ---------------------------------------------------------------------------
# Fallback chain tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mistral_success_no_openai_called():
    """When Mistral succeeds, OpenAI should never be called."""
    from app.classify import classify_document_text

    call_count = 0

    def fake_classify(endpoint, api_key, model, text, filename, timeout):
        nonlocal call_count
        call_count += 1
        return _ok_clf(), _ok_extract()

    with patch("app.classify.MISTRAL_API_KEY", "mistral-key"):
        with patch("app.classify.OPENAI_API_KEY", "openai-key"):
            with patch("app.classify._classify_with_provider", side_effect=fake_classify):
                result = await classify_document_text(
                    text="capital call notice Q1 2026",
                    filename="q1_capital_call.pdf",
                )

    assert result.fallback is False
    assert result.provider_used == "mistral"
    assert call_count == 1  # Only Mistral was called


@pytest.mark.asyncio
async def test_mistral_fails_openai_succeeds():
    """When Mistral fails, OpenAI is the fallback and succeeds."""
    from app.classify import classify_document_text

    call_sequence = []

    def fake_classify(endpoint, api_key, model, text, filename, timeout):
        call_sequence.append(model)
        if "mistral" in endpoint:
            raise ConnectionError("Mistral unreachable")
        # OpenAI call
        return _ok_clf(), _ok_extract()

    with patch("app.classify.MISTRAL_API_KEY", "mistral-key"):
        with patch("app.classify.OPENAI_API_KEY", "openai-key"):
            with patch("app.classify._classify_with_provider", side_effect=fake_classify):
                result = await classify_document_text(
                    text="capital call notice Q1 2026",
                    filename="capital_call.pdf",
                )

    assert result.fallback is False
    assert result.provider_used == "openai"
    assert result.document_type == "capital_call_notice"
    assert len(call_sequence) == 2


@pytest.mark.asyncio
async def test_mistral_and_openai_fail_heuristic_fires():
    """When both AI providers fail, heuristic classification runs."""
    from app.classify import classify_document_text

    with patch("app.classify.MISTRAL_API_KEY", "mistral-key"):
        with patch("app.classify.OPENAI_API_KEY", "openai-key"):
            with patch("app.classify._classify_with_provider",
                       side_effect=Exception("All providers down")):
                result = await classify_document_text(
                    text="capital call drawdown notice from fund",
                    filename="capital_call_q1.pdf",
                )

    assert result.fallback is True
    assert result.provider_used == "heuristic"
    assert result.document_type == "capital_call_notice"  # heuristic detects from filename
    assert result.confidence == 0.0
    assert result.classification_error is not None
    assert "mistral" in result.classification_error or "openai" in result.classification_error


@pytest.mark.asyncio
async def test_no_api_keys_goes_straight_to_heuristic():
    """With no API keys configured, heuristic runs immediately."""
    from app.classify import classify_document_text

    with patch("app.classify.MISTRAL_API_KEY", ""):
        with patch("app.classify.OPENAI_API_KEY", ""):
            result = await classify_document_text(
                text="side letter agreement modifying LPA terms",
                filename="side_letter.pdf",
            )

    assert result.fallback is True
    assert result.provider_used == "heuristic"
    assert result.document_type == "side_letter"


@pytest.mark.asyncio
async def test_heuristic_capital_call_populates_zero_fields():
    """Heuristic fallback for capital_call_notice populates all fields with confidence 0.0."""
    from app.classify import classify_document_text

    with patch("app.classify.MISTRAL_API_KEY", ""):
        with patch("app.classify.OPENAI_API_KEY", ""):
            result = await classify_document_text(
                text="capital call notice drawdown",
                filename="capital_call.pdf",
            )

    assert result.fallback is True
    assert result.document_type == "capital_call_notice"
    assert result.extracted_fields is not None

    for f in CAPITAL_CALL_FIELDS:
        assert f in result.extracted_fields
        assert result.extracted_fields[f]["confidence"] == 0.0
        assert result.extracted_fields[f]["value"] is None


@pytest.mark.asyncio
async def test_openai_only_no_mistral_key():
    """With only OPENAI_API_KEY set, OpenAI is used as primary."""
    from app.classify import classify_document_text

    with patch("app.classify.MISTRAL_API_KEY", ""):
        with patch("app.classify.OPENAI_API_KEY", "openai-key"):
            with patch("app.classify._classify_with_provider",
                       return_value=(_ok_clf(doc_type="k1", confidence=0.88), None)):
                result = await classify_document_text(
                    text="Schedule K-1 tax document",
                    filename="k1.pdf",
                )

    assert result.fallback is False
    assert result.provider_used == "openai"
    assert result.document_type == "k1"
    assert result.extracted_fields is None


@pytest.mark.asyncio
async def test_provider_used_logged_in_result():
    """provider_used field is set correctly in ClassificationResult."""
    from app.classify import classify_document_text

    with patch("app.classify.MISTRAL_API_KEY", "mistral-key"):
        with patch("app.classify.OPENAI_API_KEY", ""):
            with patch("app.classify._classify_with_provider",
                       return_value=(_ok_clf(), _ok_extract())):
                result = await classify_document_text(
                    text="capital call",
                    filename="call.pdf",
                )

    assert result.provider_used == "mistral"
    assert result.model_version == "mistral-small-latest"
