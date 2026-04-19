"""SQLAlchemy 2.0 typed models — Arukai Capital Call v0.2 (POR-147 / ARU-17-B1).

Changes from v0.1:
- User.role enum expanded to include 'approver'
- Package: new 'state' column (6-value enum), 'legacy_status' (renamed from status),
  'version' (optimistic locking), 'claimed_by_user_id', 'claimed_at', 'last_moved_at',
  'exception_reason'
- Classification: 'extracted_fields' JSONB, 'is_current' bool, unique constraint removed
- New table ReviewerNote (append-only, supersedes_note_id self-FK)
- New table RejectionDecision (separate from Approval per S4)
- AuditEvent: package_id ondelete changed to RESTRICT via migration
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# 1. Users
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        # S2: added 'approver' as third enum value
        Enum("admin", "reviewer", "approver", name="user_role"), nullable=False, default="reviewer"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    packages: Mapped[list["Package"]] = relationship("Package", back_populates="uploader", foreign_keys="Package.uploaded_by")
    claimed_packages: Mapped[list["Package"]] = relationship("Package", back_populates="claimed_by_user", foreign_keys="Package.claimed_by_user_id")
    sessions: Mapped[list["Session"]] = relationship("Session", back_populates="user")
    approvals: Mapped[list["Approval"]] = relationship("Approval", back_populates="decided_by_user")
    audit_events: Mapped[list["AuditEvent"]] = relationship("AuditEvent", back_populates="actor")
    review_notes: Mapped[list["ReviewerNote"]] = relationship("ReviewerNote", back_populates="author", foreign_keys="ReviewerNote.author_user_id")


# ---------------------------------------------------------------------------
# 2. Packages
# ---------------------------------------------------------------------------

class Package(Base):
    __tablename__ = "packages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # v0.2: new 6-state enum column (replaces status)
    state: Mapped[str] = mapped_column(
        Enum(
            "submitted",
            "intake_complete",
            "under_review",
            "routed_for_approval",
            "decision_recorded",
            "exception_surfaced",
            name="package_state",
        ),
        nullable=False,
        default="submitted",
        index=True,
    )

    # legacy_status: kept for one sprint (renamed from status per spec §2.3 / R13)
    legacy_status: Mapped[Optional[str]] = mapped_column(
        Enum(
            "pending_classification",
            "pending_review",
            "approved",
            "rejected",
            name="package_status",
        ),
        nullable=True,
    )

    # v0.2: optimistic locking (R2)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # v0.2: claim model (S1)
    claimed_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # v0.2: exception reason
    exception_reason: Mapped[Optional[str]] = mapped_column(
        Enum(
            "low_confidence",
            "missing_field",
            "extraction_failure",
            name="exception_reason_enum",
        ),
        nullable=True,
    )

    # v0.2: last state movement timestamp
    last_moved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    uploader: Mapped[User] = relationship("User", back_populates="packages", foreign_keys=[uploaded_by])
    claimed_by_user: Mapped[Optional[User]] = relationship("User", back_populates="claimed_packages", foreign_keys=[claimed_by_user_id])
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="package")
    # Approval is now one-to-many (B-Q4: drop unique, add is_final)
    approvals: Mapped[list["Approval"]] = relationship("Approval", back_populates="package")
    audit_events: Mapped[list["AuditEvent"]] = relationship("AuditEvent", back_populates="package")
    review_notes: Mapped[list["ReviewerNote"]] = relationship("ReviewerNote", back_populates="package")


# ---------------------------------------------------------------------------
# 3. Documents
# ---------------------------------------------------------------------------

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    package_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False, default="application/pdf")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    package: Mapped[Package] = relationship("Package", back_populates="documents")
    # v0.2: one-to-many classifications (R7 — remove unique, preserve history)
    classifications: Mapped[list["Classification"]] = relationship(
        "Classification", back_populates="document"
    )


# ---------------------------------------------------------------------------
# 4. Classifications (one-to-many per document, is_current flag)
# ---------------------------------------------------------------------------

class Classification(Base):
    __tablename__ = "classifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        # unique=True REMOVED per R7 — classification history must be preserved
        index=True,
    )
    # v0.2: is_current flag — only the latest extraction is current
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    document_type: Mapped[str] = mapped_column(
        Enum(
            "capital_call_notice",
            "subscription_agreement",
            "side_letter",
            "k1",
            "wire_instructions",
            "other",
            name="document_type_enum",
        ),
        nullable=False,
        default="other",
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    key_indicators: Mapped[Any] = mapped_column(JSON, nullable=True)
    # v0.2: per-field confidence (S3, spec §4)
    extracted_fields: Mapped[Any] = mapped_column(JSON, nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    classification_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    document: Mapped[Document] = relationship("Document", back_populates="classifications")


# ---------------------------------------------------------------------------
# 5. Approvals (one-to-many, is_final flag per B-Q4)
# ---------------------------------------------------------------------------

class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    package_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("packages.id", ondelete="CASCADE"),
        nullable=False,
        # unique=True REMOVED per B-Q4 — round-trips need multiple approval rows
        index=True,
    )
    decided_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    decision: Mapped[str] = mapped_column(
        Enum("approved", "rejected", name="approval_decision"), nullable=False
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # v0.2: marks the authoritative final decision (after round-trips)
    is_final: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    package: Mapped[Package] = relationship("Package", back_populates="approvals")
    decided_by_user: Mapped[User] = relationship("User", back_populates="approvals")


# ---------------------------------------------------------------------------
# 6. ReviewerNote (append-only, supersedes_note_id self-FK per R5)
# ---------------------------------------------------------------------------

class ReviewerNote(Base):
    __tablename__ = "reviewer_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    package_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # supersedes_note_id: nullable self-FK for correction chain (R5)
    supersedes_note_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("reviewer_notes.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    package: Mapped[Package] = relationship("Package", back_populates="review_notes")
    author: Mapped[User] = relationship("User", back_populates="review_notes", foreign_keys=[author_user_id])
    superseded_note: Mapped[Optional["ReviewerNote"]] = relationship(
        "ReviewerNote",
        foreign_keys=[supersedes_note_id],
        remote_side="ReviewerNote.id",
    )


# ---------------------------------------------------------------------------
# 7. Audit Events (append-only — R9, R10)
# ---------------------------------------------------------------------------

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # R10: ondelete RESTRICT — packages in terminal state must not be deletable
    # SQLite does not enforce FK constraints by default; RESTRICT is applied in migration
    package_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("packages.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    actor_user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    before_state: Mapped[Any] = mapped_column(JSON, nullable=True)
    after_state: Mapped[Any] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, index=True
    )

    package: Mapped[Optional["Package"]] = relationship("Package", back_populates="audit_events")
    actor: Mapped[Optional["User"]] = relationship("User", back_populates="audit_events")


# ---------------------------------------------------------------------------
# 8. Sessions (JWT revocation store)
# ---------------------------------------------------------------------------

class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    refresh_token_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="sessions")
