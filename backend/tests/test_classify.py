"""TDD: Classification pipeline tests — mock Anthropic, happy path, fallback."""
import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.classify import classify_document_text, ClassificationResult


# ---------------------------------------------------------------------------
# Unit tests for classify_document_text()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_happy_path():
    """Haiku returns valid JSON → classification result populated."""
    mock_response_text = json.dumps({
        "document_type": "capital_call_notice",
        "confidence": 0.94,
        "key_indicators": ["capital call", "Q2 2026", "fund manager"],
    })

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=mock_response_text)]

    with patch("app.classify.anthropic_client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_message)

        result = await classify_document_text(
            text="Capital Call Notice Q2 2026 from Meridian Fund III",
            filename="capital_call.pdf",
        )

    assert result.document_type == "capital_call_notice"
    assert result.confidence == pytest.approx(0.94)
    assert result.fallback is False
    assert result.classification_error is None


@pytest.mark.asyncio
async def test_classify_fallback_on_api_error():
    """If Anthropic raises, fallback fires — no crash."""
    with patch("app.classify.anthropic_client") as mock_client:
        mock_client.messages.create = AsyncMock(side_effect=Exception("API unavailable"))

        result = await classify_document_text(
            text="Some document text",
            filename="unknown.pdf",
        )

    assert result.fallback is True
    assert result.document_type == "other"
    assert result.confidence == 0.0
    assert result.classification_error is not None


@pytest.mark.asyncio
async def test_classify_fallback_on_invalid_json():
    """If Haiku returns non-JSON, fallback fires."""
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Sorry, I cannot classify this.")]

    with patch("app.classify.anthropic_client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_message)

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
    mock_response_text = json.dumps({
        "document_type": "other",
        "confidence": 0.3,
        "key_indicators": [],
    })

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=mock_response_text)]

    with patch("app.classify.anthropic_client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_message)

        result = await classify_document_text(
            text="capital call notice fund investment",
            filename="capital_call_q2.pdf",
        )

    # Should still return a result, fallback=True since confidence < 0.5
    assert result is not None
    assert result.fallback is True


@pytest.mark.asyncio
async def test_classify_subscription_document():
    """Correctly identifies subscription agreement."""
    mock_response_text = json.dumps({
        "document_type": "subscription_agreement",
        "confidence": 0.88,
        "key_indicators": ["subscription", "investor", "limited partnership"],
    })

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=mock_response_text)]

    with patch("app.classify.anthropic_client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_message)

        result = await classify_document_text(
            text="Subscription Agreement for Meridian Fund III LP",
            filename="subscription.pdf",
        )

    assert result.document_type == "subscription_agreement"
    assert result.confidence > 0.5


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
    """After upload, classification is attached to the package (may be fallback if no API key)."""
    token = _login(client, "admin@arukai.example", "admin123")
    mock_response_text = json.dumps({
        "document_type": "capital_call_notice",
        "confidence": 0.91,
        "key_indicators": ["capital call"],
    })
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=mock_response_text)]

    with patch("app.classify.anthropic_client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_message)

        pdf = io.BytesIO(_make_pdf_bytes())
        resp = client.post(
            "/packages",
            data={"title": "Classify Integration Test"},
            files={"file": ("capital.pdf", pdf, "application/pdf")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 201
    pkg_id = resp.json()["id"]

    detail = client.get(f"/packages/{pkg_id}", headers={"Authorization": f"Bearer {token}"})
    assert detail.status_code == 200
    detail_data = detail.json()
    docs = detail_data.get("documents", [])
    assert len(docs) > 0
    # Classification should be attached to the document
    doc = docs[0]
    assert "classification" in doc
    clf = doc["classification"]
    assert clf is not None
    assert clf["document_type"] == "capital_call_notice"
