"""SQLAlchemy 2.0 typed models — 6 tables for Arukai Capital Call v0.1."""
import uuid
from datetime import datetime, timezone
from typing import Any

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
        Enum("admin", "reviewer", name="user_role"), nullable=False, default="reviewer"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    packages: Mapped[list["Package"]] = relationship("Package", back_populates="uploader")
    sessions: Mapped[list["Session"]] = relationship("Session", back_populates="user")
    approvals: Mapped[list["Approval"]] = relationship("Approval", back_populates="decided_by_user")
    audit_events: Mapped[list["AuditEvent"]] = relationship("AuditEvent", back_populates="actor")


# ---------------------------------------------------------------------------
# 2. Packages (the upload unit — contains one or more documents)
# ---------------------------------------------------------------------------

class Package(Base):
    __tablename__ = "packages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Enum(
            "pending_classification",
            "pending_review",
            "approved",
            "rejected",
            name="package_status",
        ),
        nullable=False,
        default="pending_classification",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    uploader: Mapped[User] = relationship("User", back_populates="packages")
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="package")
    approval: Mapped["Approval | None"] = relationship("Approval", back_populates="package", uselist=False)
    audit_events: Mapped[list["AuditEvent"]] = relationship("AuditEvent", back_populates="package")


# ---------------------------------------------------------------------------
# 3. Documents (raw file storage)
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
    classification: Mapped["Classification | None"] = relationship(
        "Classification", back_populates="document", uselist=False
    )


# ---------------------------------------------------------------------------
# 4. Classifications
# ---------------------------------------------------------------------------

class Classification(Base):
    __tablename__ = "classifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
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
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    classification_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    document: Mapped[Document] = relationship("Document", back_populates="classification")


# ---------------------------------------------------------------------------
# 5. Approvals
# ---------------------------------------------------------------------------

class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    package_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("packages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    decided_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    decision: Mapped[str] = mapped_column(
        Enum("approved", "rejected", name="approval_decision"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    package: Mapped[Package] = relationship("Package", back_populates="approval")
    decided_by_user: Mapped[User] = relationship("User", back_populates="approvals")


# ---------------------------------------------------------------------------
# 6. Audit Events (append-only)
# ---------------------------------------------------------------------------

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    package_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("packages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    before_state: Mapped[Any] = mapped_column(JSON, nullable=True)
    after_state: Mapped[Any] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    package: Mapped["Package | None"] = relationship("Package", back_populates="audit_events")
    actor: Mapped["User | None"] = relationship("User", back_populates="audit_events")


# ---------------------------------------------------------------------------
# 7. Sessions (JWT revocation store)
# ---------------------------------------------------------------------------

class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="sessions")
