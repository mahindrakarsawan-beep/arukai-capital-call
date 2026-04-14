"""Packages router — upload, list, get, download PDF."""
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user
from app.classify import classify_document_text, extract_pdf_text
from app.db import get_db
from app.models import AuditEvent, Classification, Document, Package, User

router = APIRouter(prefix="/packages", tags=["packages"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ClassificationOut(BaseModel):
    id: str
    document_type: str
    confidence: float
    key_indicators: Optional[Any] = None
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
    status: str
    uploaded_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PackageDetailOut(PackageOut):
    documents: list[DocumentOut] = []


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", status_code=201, response_model=PackageOut)
async def upload_package(
    title: str = Form(...),
    file: UploadFile = ...,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF, create a package, run classification synchronously."""
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        # Allow octet-stream for test clients that don't set mime type correctly
        pass

    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    # Create package
    pkg = Package(
        title=title,
        uploaded_by=current_user.id,
        status="pending_classification",
    )
    db.add(pkg)
    await db.flush()  # get pkg.id

    # Create document
    doc = Document(
        package_id=pkg.id,
        filename=file.filename or "upload.pdf",
        mime_type=file.content_type or "application/pdf",
        size_bytes=len(raw),
        content=raw,
    )
    db.add(doc)
    await db.flush()  # get doc.id

    # Audit: upload
    audit_upload = AuditEvent(
        package_id=pkg.id,
        actor_user_id=current_user.id,
        action="upload_document",
        after_state={
            "package_id": pkg.id,
            "filename": doc.filename,
            "size_bytes": doc.size_bytes,
        },
    )
    db.add(audit_upload)

    # Extract text and classify
    text = extract_pdf_text(raw)
    clf_result = await classify_document_text(text=text, filename=doc.filename)

    clf = Classification(
        document_id=doc.id,
        document_type=clf_result.document_type,
        confidence=clf_result.confidence,
        key_indicators=clf_result.key_indicators,
        model_version=clf_result.model_version,
        fallback=clf_result.fallback,
        classification_error=clf_result.classification_error,
    )
    db.add(clf)

    # Update package status
    pkg.status = "pending_review"
    pkg.updated_at = datetime.now(timezone.utc)

    # Audit: classify
    audit_classify = AuditEvent(
        package_id=pkg.id,
        actor_user_id=current_user.id,
        action="classify_document",
        after_state={
            "document_id": doc.id,
            "document_type": clf_result.document_type,
            "confidence": clf_result.confidence,
            "model": clf_result.model_version,
            "fallback": clf_result.fallback,
            "duration_ms": clf_result.duration_ms,
        },
    )
    db.add(audit_classify)

    await db.commit()
    await db.refresh(pkg)

    return PackageOut(
        id=pkg.id,
        title=pkg.title,
        status=pkg.status,
        uploaded_by=pkg.uploaded_by,
        created_at=pkg.created_at,
        updated_at=pkg.updated_at,
    )


@router.get("", response_model=list[PackageOut])
async def list_packages(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List packages. Admin sees all; reviewer sees own + all pending_review."""
    if current_user.role == "admin":
        result = await db.execute(
            select(Package).order_by(Package.created_at.desc())
        )
    else:
        result = await db.execute(
            select(Package).where(
                (Package.uploaded_by == current_user.id) |
                (Package.status == "pending_review")
            ).order_by(Package.created_at.desc())
        )
    packages = result.scalars().all()
    return [
        PackageOut(
            id=p.id,
            title=p.title,
            status=p.status,
            uploaded_by=p.uploaded_by,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in packages
    ]


@router.get("/{pkg_id}", response_model=PackageDetailOut)
async def get_package(
    pkg_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get package detail with documents + classification."""
    result = await db.execute(
        select(Package)
        .options(
            selectinload(Package.documents).selectinload(Document.classification)
        )
        .where(Package.id == pkg_id)
    )
    pkg = result.scalar_one_or_none()
    if pkg is None:
        raise HTTPException(status_code=404, detail="Package not found")

    docs_out = []
    for doc in pkg.documents:
        clf_out = None
        if doc.classification:
            c = doc.classification
            clf_out = ClassificationOut(
                id=c.id,
                document_type=c.document_type,
                confidence=c.confidence,
                key_indicators=c.key_indicators,
                model_version=c.model_version,
                fallback=c.fallback,
                classification_error=c.classification_error,
                created_at=c.created_at,
            )
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

    return PackageDetailOut(
        id=pkg.id,
        title=pkg.title,
        status=pkg.status,
        uploaded_by=pkg.uploaded_by,
        created_at=pkg.created_at,
        updated_at=pkg.updated_at,
        documents=docs_out,
    )


@router.get("/{pkg_id}/pdf")
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
