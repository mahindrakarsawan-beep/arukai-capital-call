"""Packages router v0.2 — upload, list, get, download PDF, claim/release,
transition, review notes, attest.  (POR-147 / ARU-17-B1)
"""
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user, require_role
from app.classify import classify_document_text, extract_pdf_text
from app.db import get_db
from app.models import (
    Approval,
    AuditEvent,
    Classification,
    Document,
    Package,
    ReviewerNote,
    User,
)
from app.schemas import AuditEventOut
from app.state_machine import (
    DECISION_RECORDED,
    INTAKE_COMPLETE,
    ROUTED_FOR_APPROVAL,
    SUBMITTED,
    UNDER_REVIEW,
    InvalidTransition,
    InsufficientRole,
    validate_transition,
)

router = APIRouter(prefix="/packages", tags=["packages"])

# Keep the old /documents prefix alive for backward compatibility
legacy_router = APIRouter(prefix="/documents", tags=["documents-legacy"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ClassificationOut(BaseModel):
    id: str
    document_type: str
    confidence: float
    key_indicators: Optional[Any] = None
    extracted_fields: Optional[Any] = None
    is_current: bool = True
    model_version: Optional[str] = None
    fallback: bool
    classification_error: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentOut(BaseModel):
    id: str
    filename: str
    mime_type: str
    size_bytes: int
    created_at: datetime
    classification: Optional[ClassificationOut] = None

    model_config = {"from_attributes": True}


class PackageOut(BaseModel):
    id: str
    title: str
    state: str
    legacy_status: Optional[str] = None
    uploaded_by: str
    version: int
    claimed_by_user_id: Optional[str] = None
    claimed_at: Optional[datetime] = None
    exception_reason: Optional[str] = None
    last_moved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PackageListOut(BaseModel):
    """Slimmed list response that includes classification summary from first document."""
    id: str
    title: str
    state: str
    legacy_status: Optional[str] = None
    uploaded_by: str
    claimed_by_user_id: Optional[str] = None
    claimed_at: Optional[datetime] = None
    last_moved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # Classification summary from first document's current classification
    doc_type: Optional[str] = None
    confidence: Optional[float] = None
    filename: Optional[str] = None  # from first document
    ai_summary: Optional[str] = None  # one-line AI intelligence summary

    model_config = {"from_attributes": True}


class ReviewNoteOut(BaseModel):
    id: str
    package_id: str
    author_user_id: str
    body: str
    supersedes_note_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalOut(BaseModel):
    id: str
    package_id: str
    decision: str
    note: Optional[str] = None
    is_final: bool
    decided_at: datetime
    decided_by: str

    model_config = {"from_attributes": True}


class PackageDetailOut(PackageOut):
    documents: list[DocumentOut] = []
    review_notes: list[ReviewNoteOut] = []
    audit_trail: list[AuditEventOut] = []
    approval: Optional[ApprovalOut] = None
    # AI analysis fields surfaced from first document's current classification
    extracted_fields: Optional[dict] = None
    classification_reasoning: Optional[str] = None
    model_used: Optional[str] = None
    classification_duration_ms: Optional[int] = None


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class TransitionRequest(BaseModel):
    to_state: str
    reason: Optional[str] = None


class ReviewNoteRequest(BaseModel):
    body: str
    supersedes_note_id: Optional[str] = None


class AttestRequest(BaseModel):
    action: str  # "approved" | "rejected"
    note: Optional[str] = None


class ClaimRequest(BaseModel):
    pass  # No body needed


# ── Intake-status response models (POR-159 19d.2) ──────────────────────────────

class IntakeStepReceive(BaseModel):
    filesize: Optional[str] = None       # human-readable, e.g. "2.4 MB"
    mime_type: Optional[str] = None      # e.g. "application/pdf"


class IntakeStepClassify(BaseModel):
    doc_type: Optional[str] = None       # formatted, e.g. "Capital Call Notice"
    confidence: Optional[float] = None   # 0.0–1.0
    pending: bool = False                # true while classification in progress


class IntakeStepExtract(BaseModel):
    total_fields: Optional[int] = None   # count of resolved fields (value != None)
    max_fields: Optional[int] = None     # total fields in the schema (denominator)
    flagged_count: Optional[int] = None  # fields with confidence < 0.80


class IntakeStepReady(BaseModel):
    next_owner: Optional[str] = None     # e.g. "reviewer", "approver", "complete"


class IntakeStatusOut(BaseModel):
    current_step: int                    # 1..4 — which step is active
    receive: Optional[IntakeStepReceive] = None
    classify: Optional[IntakeStepClassify] = None
    extract: Optional[IntakeStepExtract] = None
    ready: Optional[IntakeStepReady] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_current_classification(doc: Document) -> Optional[Classification]:
    """Return the is_current=True classification for a document, or None."""
    for clf in doc.classifications:
        if clf.is_current:
            return clf
    return None


def _format_filesize(size_bytes: Optional[int]) -> Optional[str]:
    """Return '2.4 MB', '512 KB', '89 B', or None."""
    if size_bytes is None or size_bytes < 0:
        return None
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.0f} KB"
    return f"{size_bytes} B"


# POR-159 19d.1 — human-readable doc-type display (drops "Notice"/"Agreement" suffixes).
DOC_TYPE_DISPLAY: dict[str, str] = {
    "capital_call_notice": "Capital Call",
    "subscription_agreement": "Subscription",
    "side_letter": "Side Letter",
    "k1": "K-1",
    "wire_instructions": "Wire Instructions",
    "other": "Document",
}


def _format_amount(raw: Any) -> Optional[str]:
    """Currency summary: 120000000 → '$120M', 12500 → '$12K', 89 → '$89', bad → None.

    Preserves sign, strips symbols/commas/whitespace on string input, passes through
    already-formatted like '120M' by prefixing '$'. Returns None on parse failure so
    the caller can drop the segment cleanly rather than render '$None'.
    """
    if raw is None or raw == "":
        return None
    try:
        if isinstance(raw, str):
            s = raw.replace("$", "").replace("€", "").replace("£", "").replace(",", "").strip()
            if not s:
                return None
            # Already in short form like "120M" / "12K" / "-120M"
            if s.endswith(("M", "m", "K", "k")):
                return f"${s[:-1]}{s[-1].upper()}"
            amount = float(s)
        else:
            amount = float(raw)
    except (ValueError, TypeError):
        return None

    sign = "-" if amount < 0 else ""
    absamt = abs(amount)
    if absamt >= 1_000_000:
        return f"{sign}${int(absamt / 1_000_000)}M"
    if absamt >= 1_000:
        return f"{sign}${int(absamt / 1_000)}K"
    return f"{sign}${int(absamt)}"


def _format_due_date(raw: Any) -> Optional[str]:
    """ISO date → 'May 15' (current year) or 'May 15, 2027' (other year). None on fail."""
    if not raw:
        return None
    try:
        date_str = str(raw).split("T")[0]
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    if d.year == datetime.now(timezone.utc).year:
        return d.strftime("%b %d")
    return d.strftime("%b %d, %Y")


def _build_ai_summary(clf: Optional[Classification]) -> str:
    """Generate a one-line AI intelligence summary from a classification record.

    Target format (POR-149):
      "Capital Call · $120M due May 15 · 8 fields extracted · 99% confidence · 1 flagged"

    Segments drop gracefully when their data is missing (amount/date parse fail,
    no fields extracted, etc.).
    """
    if not clf:
        return "Awaiting classification"

    doc_type_key = clf.document_type or ""
    doc_type = DOC_TYPE_DISPLAY.get(
        doc_type_key, doc_type_key.replace("_", " ").title() or "Document"
    )
    parts = [doc_type]

    fields = clf.extracted_fields or {}

    # Amount + date segment
    amount = None
    due_date = None
    if isinstance(fields.get("amount_due"), dict):
        amount = _format_amount(fields["amount_due"].get("value"))
    if isinstance(fields.get("due_date"), dict):
        due_date = _format_due_date(fields["due_date"].get("value"))

    if amount and due_date:
        parts.append(f"{amount} due {due_date}")
    elif amount:
        parts.append(amount)
    elif due_date:
        parts.append(f"due {due_date}")

    # Field count segment (resolved fields only)
    field_count = sum(
        1 for f in fields.values()
        if isinstance(f, dict) and f.get("value") is not None
    )
    if field_count > 0:
        parts.append(f"{field_count} fields extracted")

    # Confidence segment
    parts.append(f"{int(clf.confidence * 100)}% confidence")

    # Flagged segment — threshold matches frontend AIAnalysisBlock 0.80 (POR-148 spec)
    flagged = sum(
        1 for f in fields.values()
        if isinstance(f, dict) and f.get("confidence", 1) < 0.80
    )
    parts.append(f"{flagged} flagged" if flagged else "0 flags")

    return " · ".join(parts)


def _build_classification_reasoning(clf: Optional[Classification]) -> Optional[str]:
    """Compose a natural-language reasoning string from key_indicators."""
    if not clf:
        return None
    indicators = clf.key_indicators
    if not indicators:
        return None
    if isinstance(indicators, list) and len(indicators) > 0:
        return "Classified based on: " + "; ".join(str(i) for i in indicators[:5])
    return None


async def _write_audit(
    db: AsyncSession,
    package_id: str,
    actor_user_id: Optional[str],
    action: str,
    before_state: Optional[dict] = None,
    after_state: Optional[dict] = None,
) -> None:
    event = AuditEvent(
        package_id=package_id,
        actor_user_id=actor_user_id,
        action=action,
        before_state=before_state,
        after_state=after_state,
    )
    db.add(event)


async def _get_package_or_404(db: AsyncSession, pkg_id: str) -> Package:
    result = await db.execute(select(Package).where(Package.id == pkg_id))
    pkg = result.scalar_one_or_none()
    if pkg is None:
        raise HTTPException(status_code=404, detail="Package not found")
    return pkg


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@router.post("/upload", status_code=201, response_model=PackageOut)
@legacy_router.post("/upload", status_code=201, response_model=PackageOut)
async def upload_package(
    title: str = Form(...),
    file: UploadFile = ...,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF, create a package, run classification synchronously."""
    from app.security import validate_pdf

    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    is_valid, reason = validate_pdf(raw, file.filename or "unknown.pdf")
    if not is_valid:
        raise HTTPException(status_code=400, detail=reason)

    now = datetime.now(timezone.utc)

    # Create package in SUBMITTED state
    pkg = Package(
        title=title,
        uploaded_by=current_user.id,
        state=SUBMITTED,
        legacy_status="pending_classification",
        version=1,
        last_moved_at=now,
    )
    db.add(pkg)
    await db.flush()

    # Create document
    doc = Document(
        package_id=pkg.id,
        filename=file.filename or "upload.pdf",
        mime_type=file.content_type or "application/pdf",
        size_bytes=len(raw),
        content=raw,
    )
    db.add(doc)
    await db.flush()

    # Audit: upload
    await _write_audit(
        db, pkg.id, current_user.id, "upload_document",
        after_state={"package_id": pkg.id, "filename": doc.filename, "size_bytes": doc.size_bytes},
    )

    # Classify
    text = extract_pdf_text(raw)
    clf_result = await classify_document_text(text=text, filename=doc.filename)

    clf = Classification(
        document_id=doc.id,
        document_type=clf_result.document_type,
        confidence=clf_result.confidence,
        key_indicators=clf_result.key_indicators,
        extracted_fields=clf_result.extracted_fields,
        model_version=clf_result.model_version,
        fallback=clf_result.fallback,
        classification_error=clf_result.classification_error,
        is_current=True,
    )
    db.add(clf)

    # System state transition: submitted → intake_complete or exception_surfaced
    from app.state_machine import EXCEPTION_SURFACED, INTAKE_COMPLETE  # noqa

    # Treat NULL confidence as 0.0 (R12)
    effective_confidence = clf_result.confidence if clf_result.confidence is not None else 0.0

    if effective_confidence >= 0.5 and not clf_result.fallback:
        new_state = INTAKE_COMPLETE
        exception_reason = None
        legacy = "pending_review"
    else:
        new_state = EXCEPTION_SURFACED
        exception_reason = "low_confidence" if effective_confidence < 0.5 else "extraction_failure"
        legacy = "pending_review"

    pkg.state = new_state
    pkg.legacy_status = legacy
    pkg.exception_reason = exception_reason
    pkg.last_moved_at = datetime.now(timezone.utc)
    pkg.updated_at = datetime.now(timezone.utc)

    # Audit: classify + system transition
    await _write_audit(
        db, pkg.id, current_user.id, "classify_document",
        after_state={
            "document_id": doc.id,
            "document_type": clf_result.document_type,
            "confidence": clf_result.confidence,
            "model": clf_result.model_version,
            "fallback": clf_result.fallback,
            "duration_ms": clf_result.duration_ms,
        },
    )
    await _write_audit(
        db, pkg.id, None, "system_transition",
        before_state={"state": SUBMITTED},
        after_state={"state": new_state, "exception_reason": exception_reason},
    )

    await db.commit()
    await db.refresh(pkg)
    return pkg


# ---------------------------------------------------------------------------
# List packages
# ---------------------------------------------------------------------------

@router.get("", response_model=list[PackageListOut])
@legacy_router.get("", response_model=list[PackageListOut])
async def list_packages(
    state: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List packages with optional state filter. All roles see all packages.
    Role gates ACTIONS (claim/attest), not visibility.
    """
    q = (
        select(Package)
        .options(
            selectinload(Package.documents).selectinload(Document.classifications),
        )
    )

    # Visibility: everyone sees all packages — role gates actions, not visibility
    # (admin previously restricted to own uploads — that was inverted, now fixed)

    if state:
        q = q.where(Package.state == state)

    q = q.order_by(Package.created_at.desc())
    result = await db.execute(q)
    packages = result.scalars().all()

    out = []
    for pkg in packages:
        # Extract classification summary from first document's current classification
        doc_type: Optional[str] = None
        confidence: Optional[float] = None
        filename: Optional[str] = None

        clf = None
        if pkg.documents:
            first_doc = pkg.documents[0]
            filename = first_doc.filename
            clf = _get_current_classification(first_doc)
            if clf:
                doc_type = clf.document_type
                confidence = clf.confidence

        out.append(
            PackageListOut(
                id=pkg.id,
                title=pkg.title,
                state=pkg.state,
                legacy_status=pkg.legacy_status,
                uploaded_by=pkg.uploaded_by,
                claimed_by_user_id=pkg.claimed_by_user_id,
                claimed_at=pkg.claimed_at,
                last_moved_at=pkg.last_moved_at,
                created_at=pkg.created_at,
                updated_at=pkg.updated_at,
                doc_type=doc_type,
                confidence=confidence,
                filename=filename,
                ai_summary=_build_ai_summary(clf),
            )
        )

    return out


# ---------------------------------------------------------------------------
# Get package detail
# ---------------------------------------------------------------------------

@router.get("/{pkg_id}", response_model=PackageDetailOut)
@legacy_router.get("/{pkg_id}", response_model=PackageDetailOut)
async def get_package(
    pkg_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get package detail with documents, classifications, review notes, audit trail."""
    result = await db.execute(
        select(Package)
        .options(
            selectinload(Package.documents).selectinload(Document.classifications),
            selectinload(Package.review_notes),
            selectinload(Package.audit_events),
            selectinload(Package.approvals),
        )
        .where(Package.id == pkg_id)
    )
    pkg = result.scalar_one_or_none()
    if pkg is None:
        raise HTTPException(status_code=404, detail="Package not found")

    docs_out = []
    for doc in pkg.documents:
        clf = _get_current_classification(doc)
        clf_out = None
        if clf:
            clf_out = ClassificationOut.model_validate(clf)
        docs_out.append(
            DocumentOut(
                id=doc.id,
                filename=doc.filename,
                mime_type=doc.mime_type,
                size_bytes=doc.size_bytes,
                created_at=doc.created_at,
                classification=clf_out,
            )
        )

    notes_out = [
        ReviewNoteOut.model_validate(n)
        for n in sorted(pkg.review_notes, key=lambda n: n.created_at, reverse=True)
    ]

    audit_out = [
        AuditEventOut.model_validate(e)
        for e in sorted(pkg.audit_events, key=lambda e: e.created_at)
    ]

    # Final approval (is_final=True)
    final_approval = next((a for a in pkg.approvals if a.is_final), None)
    approval_out = ApprovalOut.model_validate(final_approval) if final_approval else None

    # AI fields from first document's current classification
    first_clf: Optional[Classification] = None
    if pkg.documents:
        first_clf = _get_current_classification(pkg.documents[0])

    return PackageDetailOut(
        id=pkg.id,
        title=pkg.title,
        state=pkg.state,
        legacy_status=pkg.legacy_status,
        uploaded_by=pkg.uploaded_by,
        version=pkg.version,
        claimed_by_user_id=pkg.claimed_by_user_id,
        claimed_at=pkg.claimed_at,
        exception_reason=pkg.exception_reason,
        last_moved_at=pkg.last_moved_at,
        created_at=pkg.created_at,
        updated_at=pkg.updated_at,
        documents=docs_out,
        review_notes=notes_out,
        audit_trail=audit_out,
        approval=approval_out,
        extracted_fields=first_clf.extracted_fields if first_clf else None,
        classification_reasoning=_build_classification_reasoning(first_clf),
        model_used=first_clf.model_version if first_clf else None,
        classification_duration_ms=None,  # duration_ms not stored in DB, available at classify time
    )


# ---------------------------------------------------------------------------
# PDF download
# ---------------------------------------------------------------------------

@router.get("/{pkg_id}/pdf")
@legacy_router.get("/{pkg_id}/pdf")
async def download_pdf(
    pkg_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream the raw PDF bytes for the first document in a package."""
    result = await db.execute(
        select(Package)
        .options(selectinload(Package.documents))
        .where(Package.id == pkg_id)
    )
    pkg = result.scalar_one_or_none()
    if pkg is None:
        raise HTTPException(status_code=404, detail="Package not found")
    if not pkg.documents:
        raise HTTPException(status_code=404, detail="No documents in package")

    doc = pkg.documents[0]
    return Response(
        content=doc.content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{doc.filename}"'},
    )


# ---------------------------------------------------------------------------
# Intake status (POR-159 19d.2) — drives IntakeCeremony real AI narration
# ---------------------------------------------------------------------------

@router.get("/{pkg_id}/intake-status", response_model=IntakeStatusOut)
async def get_package_intake_status(
    pkg_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return step-level intake state for the frontend IntakeCeremony component.

    Maps the 4-step intake ceremony (receive → classify → extract → ready) onto
    the package's current state + classification data. Each step is None until
    the underlying data is available; current_step tracks the highest populated
    step so the frontend can render the active card.
    """
    result = await db.execute(
        select(Package)
        .options(selectinload(Package.documents).selectinload(Document.classifications))
        .where(Package.id == pkg_id)
    )
    pkg = result.scalar_one_or_none()
    if pkg is None:
        raise HTTPException(status_code=404, detail="Package not found")

    doc = pkg.documents[0] if pkg.documents else None
    clf = _get_current_classification(doc) if doc else None

    # Step 1 (receive)
    receive = IntakeStepReceive(
        filesize=_format_filesize(getattr(doc, "size_bytes", None)) if doc else None,
        mime_type=doc.mime_type if doc else None,
    ) if doc else None

    # Step 2 (classify)
    if clf:
        doc_type_key = clf.document_type or ""
        classify = IntakeStepClassify(
            doc_type=DOC_TYPE_DISPLAY.get(
                doc_type_key, doc_type_key.replace("_", " ").title() or "Document"
            ),
            confidence=clf.confidence,
            pending=False,
        )
    elif doc and pkg.state == "submitted":
        classify = IntakeStepClassify(pending=True)
    else:
        classify = None

    # Step 3 (extract)
    if clf and clf.extracted_fields:
        fields = clf.extracted_fields
        total = sum(
            1 for f in fields.values()
            if isinstance(f, dict) and f.get("value") is not None
        )
        flagged = sum(
            1 for f in fields.values()
            if isinstance(f, dict) and f.get("confidence", 1) < 0.80
        )
        extract = IntakeStepExtract(
            total_fields=total,
            max_fields=len(fields),
            flagged_count=flagged,
        )
    else:
        extract = None

    # Step 4 (ready)
    if pkg.state in (
        "intake_complete", "under_review", "routed_for_approval", "decision_recorded"
    ):
        next_owner = {
            "intake_complete": "reviewer",
            "under_review": "reviewer",
            "routed_for_approval": "approver",
            "decision_recorded": "complete",
        }.get(pkg.state, "reviewer")
        ready = IntakeStepReady(next_owner=next_owner)
    else:
        ready = None

    # current_step = highest populated
    if ready is not None:
        current_step = 4
    elif extract is not None:
        current_step = 3
    elif classify is not None:
        current_step = 2
    else:
        current_step = 1

    return IntakeStatusOut(
        current_step=current_step,
        receive=receive,
        classify=classify,
        extract=extract,
        ready=ready,
    )


# ---------------------------------------------------------------------------
# Claim
# ---------------------------------------------------------------------------

@router.post("/{pkg_id}/claim", response_model=PackageOut)
async def claim_package(
    pkg_id: str,
    current_user: User = Depends(require_role("reviewer", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """Reviewer claims an unclaimed package. 409 if already claimed."""
    pkg = await _get_package_or_404(db, pkg_id)

    if pkg.claimed_by_user_id is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Package is already claimed by user {pkg.claimed_by_user_id}",
        )

    now = datetime.now(timezone.utc)
    new_state = UNDER_REVIEW if pkg.state == INTAKE_COMPLETE else pkg.state

    # Use optimistic-lock-style update so version increments
    stmt = (
        update(Package)
        .where(Package.id == pkg_id, Package.claimed_by_user_id.is_(None))
        .values(
            claimed_by_user_id=current_user.id,
            claimed_at=now,
            state=new_state,
            version=Package.version + 1,
            last_moved_at=now,
            updated_at=now,
        )
        .returning(Package.version)
    )
    result2 = await db.execute(stmt)
    new_version = result2.scalar_one_or_none()
    if new_version is None:
        # Another request claimed it between our SELECT and UPDATE
        raise HTTPException(status_code=409, detail="Package is already claimed by another user")

    pkg.claimed_by_user_id = current_user.id
    pkg.claimed_at = now
    pkg.state = new_state
    pkg.version = new_version
    pkg.last_moved_at = now
    pkg.updated_at = now

    await _write_audit(
        db, pkg.id, current_user.id, "claimed_package",
        after_state={"claimed_by_user_id": current_user.id, "state": pkg.state},
    )

    await db.commit()
    await db.refresh(pkg)
    return pkg


# ---------------------------------------------------------------------------
# Release
# ---------------------------------------------------------------------------

@router.post("/{pkg_id}/release", response_model=PackageOut)
async def release_package(
    pkg_id: str,
    current_user: User = Depends(require_role("reviewer", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """Release claim on a package. Validates no notes recorded (R4)."""
    pkg = await _get_package_or_404(db, pkg_id)

    if pkg.claimed_by_user_id is None:
        raise HTTPException(status_code=409, detail="Package is not currently claimed")

    # R4: cannot release claim after notes have been recorded
    note_count_result = await db.execute(
        select(func.count(ReviewerNote.id)).where(ReviewerNote.package_id == pkg_id)
    )
    note_count = note_count_result.scalar_one()
    if note_count > 0:
        raise HTTPException(
            status_code=409,
            detail="Cannot release claim after annotation — notes are recorded",
        )

    now = datetime.now(timezone.utc)
    pkg.claimed_by_user_id = None
    pkg.claimed_at = None
    pkg.updated_at = now

    # Transition back to intake_complete if currently under_review
    if pkg.state == UNDER_REVIEW:
        pkg.state = INTAKE_COMPLETE
        pkg.last_moved_at = now

    await _write_audit(
        db, pkg.id, current_user.id, "released_claim",
        after_state={"state": pkg.state},
    )

    await db.commit()
    await db.refresh(pkg)
    return pkg


# ---------------------------------------------------------------------------
# Transition
# ---------------------------------------------------------------------------

@router.post("/{pkg_id}/transition", response_model=PackageOut)
async def transition_package(
    pkg_id: str,
    body: TransitionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """State transition endpoint. Uses optimistic locking (version column)."""
    pkg = await _get_package_or_404(db, pkg_id)

    # Count notes for the release-claim guard (R4)
    note_count_result = await db.execute(
        select(func.count(ReviewerNote.id)).where(ReviewerNote.package_id == pkg_id)
    )
    note_count = note_count_result.scalar_one()

    try:
        validate_transition(
            from_state=pkg.state,
            to_state=body.to_state,
            actor_role=current_user.role,
            note_count=note_count,
        )
    except InvalidTransition as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )
    except InsufficientRole as exc:
        raise HTTPException(
            status_code=403,
            detail="This action is outside your workflow role.",
        )

    old_state = pkg.state
    old_version = pkg.version
    now = datetime.now(timezone.utc)

    # Optimistic locking: UPDATE WHERE version = expected_version (R2)
    stmt = (
        update(Package)
        .where(Package.id == pkg_id, Package.version == old_version)
        .values(
            state=body.to_state,
            version=old_version + 1,
            last_moved_at=now,
            updated_at=now,
        )
        .returning(Package.version)
    )
    update_result = await db.execute(stmt)
    new_version = update_result.scalar_one_or_none()

    if new_version is None:
        raise HTTPException(
            status_code=409,
            detail="Concurrent modification — reload and retry",
        )

    # Sync in-memory object
    pkg.state = body.to_state
    pkg.version = new_version
    pkg.last_moved_at = now
    pkg.updated_at = now

    await _write_audit(
        db, pkg.id, current_user.id, "transitioned_package",
        before_state={"state": old_state},
        after_state={"state": body.to_state, "reason": body.reason},
    )

    await db.commit()
    await db.refresh(pkg)
    return pkg


# ---------------------------------------------------------------------------
# Review notes
# ---------------------------------------------------------------------------

@router.post("/{pkg_id}/review-notes", status_code=201, response_model=ReviewNoteOut)
async def create_review_note(
    pkg_id: str,
    body: ReviewNoteRequest,
    current_user: User = Depends(require_role("reviewer", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """Append a reviewer note. Append-only — no PATCH/DELETE. Role: reviewer or admin."""
    if not body.body or not body.body.strip():
        raise HTTPException(status_code=422, detail="Note body must not be empty")

    pkg = await _get_package_or_404(db, pkg_id)

    # Validate supersedes_note_id if provided
    if body.supersedes_note_id:
        sup_result = await db.execute(
            select(ReviewerNote).where(
                ReviewerNote.id == body.supersedes_note_id,
                ReviewerNote.package_id == pkg_id,
            )
        )
        if sup_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Superseded note not found in this package")

    note = ReviewerNote(
        package_id=pkg_id,
        author_user_id=current_user.id,
        body=body.body.strip(),
        supersedes_note_id=body.supersedes_note_id,
    )
    db.add(note)
    await db.flush()

    await _write_audit(
        db, pkg_id, current_user.id, "recorded_review_note",
        after_state={
            "review_note_id": note.id,
            "body_excerpt": note.body[:80],
            "supersedes_note_id": note.supersedes_note_id,
        },
    )

    await db.commit()
    await db.refresh(note)
    return note


@router.get("/{pkg_id}/review-notes", response_model=list[ReviewNoteOut])
async def list_review_notes(
    pkg_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List review notes for a package (newest first). Role: any authenticated."""
    result = await db.execute(
        select(ReviewerNote)
        .where(ReviewerNote.package_id == pkg_id)
        .order_by(ReviewerNote.created_at.desc())
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Attest (approve or reject)
# ---------------------------------------------------------------------------

@router.post("/{pkg_id}/attest", response_model=ApprovalOut)
async def attest_package(
    pkg_id: str,
    body: AttestRequest,
    current_user: User = Depends(require_role("approver")),
    db: AsyncSession = Depends(get_db),
):
    """Approver attests a decision atomically. State must be routed_for_approval.
    Rejection from exception_surfaced is also accepted per spec §2.2.
    """
    if body.action not in ("approved", "rejected"):
        raise HTTPException(status_code=422, detail="action must be 'approved' or 'rejected'")

    if body.action == "rejected" and (not body.note or not body.note.strip()):
        raise HTTPException(
            status_code=422,
            detail="Attestation note required on rejection",
        )

    pkg = await _get_package_or_404(db, pkg_id)

    # Validate transition through state machine
    try:
        validate_transition(pkg.state, DECISION_RECORDED, current_user.role)
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except InsufficientRole:
        raise HTTPException(status_code=403, detail="This action is outside your workflow role.")

    old_state = pkg.state
    old_version = pkg.version
    now = datetime.now(timezone.utc)

    # Mark any existing non-final approvals as non-final
    await db.execute(
        update(Approval)
        .where(Approval.package_id == pkg_id, Approval.is_final == True)  # noqa: E712
        .values(is_final=False)
    )

    # Create new final approval
    approval = Approval(
        package_id=pkg_id,
        decided_by=current_user.id,
        decision=body.action,
        note=body.note,
        is_final=True,
        decided_at=now,
    )
    db.add(approval)
    await db.flush()

    # Optimistic lock transition to decision_recorded
    stmt = (
        update(Package)
        .where(Package.id == pkg_id, Package.version == old_version)
        .values(
            state=DECISION_RECORDED,
            version=old_version + 1,
            last_moved_at=now,
            updated_at=now,
        )
        .returning(Package.version)
    )
    update_result = await db.execute(stmt)
    new_version = update_result.scalar_one_or_none()

    if new_version is None:
        raise HTTPException(
            status_code=409,
            detail="Concurrent modification — reload and retry",
        )

    pkg.state = DECISION_RECORDED
    pkg.version = new_version

    action_name = "attested_approval" if body.action == "approved" else "recorded_rejection"
    await _write_audit(
        db, pkg_id, current_user.id, action_name,
        before_state={"state": old_state},
        after_state={
            "state": DECISION_RECORDED,
            "decision": body.action,
            "decided_by": current_user.id,
            "note_present": bool(body.note),
        },
    )

    await db.commit()
    await db.refresh(approval)
    return approval


# ---------------------------------------------------------------------------
# Deprecation bridge: POST /approvals/{pkg_id} → 410 Gone
# ---------------------------------------------------------------------------

deprecation_router = APIRouter(prefix="/approvals", tags=["approvals-deprecated"])


@deprecation_router.post("/{pkg_id}")
async def approvals_deprecated(pkg_id: str):
    """Deprecated. Use POST /packages/{id}/attest instead."""
    raise HTTPException(
        status_code=410,
        detail="This endpoint is deprecated. Use POST /packages/{id}/attest instead.",
    )
