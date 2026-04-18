"""TDD: Classification pipeline tests v0.2 — mock Mistral HTTP calls, fallback."""
import io
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.classify import classify_document_text, ClassificationResult


# ---------------------------------------------------------------------------
# Helpers — mock _classify_with_provider (the synchronous inner worker)
# ---------------------------------------------------------------------------

def _make_clf_data(
    doc_type: str = "capital_call_notice",
    confidence: float = 0.94,
    indicators: list | None = None,
) -> dict:
    return {
        "document_type": doc_type,
        "confidence": confidence,
        "key_indicators": indicators or ["capital call", "Q2 2026"],
    }


def _make_extract_data() -> dict:
    return {
        "fund_name": {"value": "Fund III", "confidence": 0.95, "source_text": "Fund III"},
        "call_number": {"value": "Q2-2026", "confidence": 0.88, "source_text": "Q2-2026"},
        "amount_due": {"value": None, "confidence": 0.0, "source_text": None},
        "currency": {"value": "USD", "confidence": 0.99, "source_text": "USD"},
        "due_date": {"value": None, "confidence": 0.0, "source_text": None},
        "recipient_entity": {"value": None, "confidence": 0.0, "source_text": None},
        "wire_instructions_present": {"value": False, "confidence": 0.7, "source_text": None},
        "notice_date": {"value": None, "confidence": 0.0, "source_text": None},
    }


# ---------------------------------------------------------------------------
# Unit tests for classify_document_text()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_happy_path():
    """Mistral returns valid result → classification populated."""
    clf_data = _make_clf_data()
    extract_data = _make_extract_data()

    with patch("app.classify._classify_with_provider", return_value=(clf_data, extract_data)):
        with patch("app.classify.MISTRAL_API_KEY", "test-key"):
            result = await classify_document_text(
                text="Capital Call Notice Q2 2026 from Meridian Fund III",
                filename="capital_call.pdf",
            )

    assert result.document_type == "capital_call_notice"
    assert result.confidence == pytest.approx(0.94)
    assert result.fallback is False
    assert result.classification_error is None
    assert result.provider_used in ("mistral", "openai")


@pytest.mark.asyncio
async def test_classify_fallback_on_api_error():
    """If all providers fail, heuristic fires — no crash."""
    with patch("app.classify.MISTRAL_API_KEY", "test-key"):
        with patch("app.classify.OPENAI_API_KEY", ""):
            with patch("app.classify._classify_with_provider", side_effect=Exception("API unavailable")):
                result = await classify_document_text(
                    text="Some document text",
                    filename="unknown.pdf",
                )

    assert result.fallback is True
    assert result.document_type == "other"
    assert result.confidence == 0.0
    assert result.classification_error is not None
    assert result.provider_used == "heuristic"


@pytest.mark.asyncio
async def test_classify_fallback_on_invalid_json():
    """If provider raises ValueError on bad JSON, fallback fires."""
    with patch("app.classify.MISTRAL_API_KEY", "test-key"):
        with patch("app.classify.OPENAI_API_KEY", ""):
            with patch("app.classify._classify_with_provider",
                       side_effect=ValueError("Failed to parse JSON")):
                result = await classify_document_text(
                    text="Some document text",
                    filename="doc.pdf",
                )

    assert result.fallback is True
    assert result.document_type in (
        "other", "capital_call_notice", "subscription_agreement",
        "side_letter", "k1", "wire_instructions",
    )


@pytest.mark.asyncio
async def test_classify_low_confidence_uses_heuristic():
    """Low confidence (<0.5) triggers heuristic fallback."""
    clf_data = _make_clf_data(doc_type="other", confidence=0.3, indicators=[])

    with patch("app.classify.MISTRAL_API_KEY", "test-key"):
        with patch("app.classify._classify_with_provider", return_value=(clf_data, None)):
            result = await classify_document_text(
                text="capital call notice fund investment",
                filename="capital_call_q2.pdf",
            )

    assert result is not None
    assert result.fallback is True


@pytest.mark.asyncio
async def test_classify_subscription_document():
    """Correctly identifies subscription agreement."""
    clf_data = _make_clf_data(
        doc_type="subscription_agreement",
        confidence=0.88,
        indicators=["subscription", "investor", "limited partnership"],
    )

    with patch("app.classify.MISTRAL_API_KEY", "test-key"):
        with patch("app.classify._classify_with_provider", return_value=(clf_data, None)):
            result = await classify_document_text(
                text="Subscription Agreement for Meridian Fund III LP",
                filename="subscription.pdf",
            )

    assert result.document_type == "subscription_agreement"
    assert result.confidence > 0.5
    # Non-capital_call_notice types don't get extracted_fields
    assert result.extracted_fields is None


# ---------------------------------------------------------------------------
# Integration: upload triggers classification (mocked)
# ---------------------------------------------------------------------------

def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _make_pdf_bytes() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 100 700 Td "
        b"(Capital Call Notice Q2 2026) Tj ET\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n0000000000 65535 f \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n9\n%%EOF\n"
    )


def test_upload_stores_classification(client: TestClient):
    """After upload, classification is attached to the package."""
    token = _login(client, "admin@arukai.example", "admin123")

    clf_data = _make_clf_data(confidence=0.91, indicators=["capital call"])
    extract_data = _make_extract_data()
    extract_data["fund_name"] = {"value": "Fund X", "confidence": 0.9, "source_text": "Fund X"}
    extract_data["call_number"] = {"value": "Q1", "confidence": 0.8, "source_text": "Q1"}

    with patch("app.classify.MISTRAL_API_KEY", "test-key"):
        with patch("app.classify._classify_with_provider", return_value=(clf_data, extract_data)):
            pdf = io.BytesIO(_make_pdf_bytes())
            resp = client.post(
                "/documents/upload",
                data={"title": "Classify Integration Test"},
                files={"file": ("capital.pdf", pdf, "application/pdf")},
                headers={"Authorization": f"Bearer {token}"},
            )

    assert resp.status_code == 201
    pkg_id = resp.json()["id"]

    detail = client.get(f"/documents/{pkg_id}", headers={"Authorization": f"Bearer {token}"})
    assert detail.status_code == 200
    detail_data = detail.json()
    docs = detail_data.get("documents", [])
    assert len(docs) > 0
    doc = docs[0]
    assert "classification" in doc
    clf = doc["classification"]
    assert clf is not None
    assert clf["document_type"] == "capital_call_notice"
