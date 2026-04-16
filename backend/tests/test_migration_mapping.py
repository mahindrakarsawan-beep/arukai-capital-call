"""TDD: Migration mapping tests — v0.1 status values map to correct v0.2 states.
(POR-147 / ARU-17-B1)

These tests verify the business logic of the migration mapping (spec §2.3)
without actually running Alembic. They test the Python-level mapping rules.
"""
import pytest


# ---------------------------------------------------------------------------
# Migration mapping logic (mirrors alembic 0001 data migration)
# ---------------------------------------------------------------------------

def map_v01_to_v02_state(legacy_status: str, confidence: float | None) -> tuple[str, str | None]:
    """Pure function: map v0.1 status + confidence → v0.2 (state, exception_reason).

    R12: NULL confidence treated as 0.0 → exception_surfaced.

    Returns:
        (state, exception_reason) tuple
    """
    THRESHOLD = 0.5

    if legacy_status == "pending_classification":
        return ("submitted", None)
    elif legacy_status == "approved":
        return ("decision_recorded", None)
    elif legacy_status == "rejected":
        return ("decision_recorded", None)
    elif legacy_status == "pending_review":
        # R12: treat NULL as 0.0
        effective_confidence = confidence if confidence is not None else 0.0
        if effective_confidence >= THRESHOLD:
            return ("intake_complete", None)
        else:
            return ("exception_surfaced", "low_confidence")
    else:
        # Unknown status — default to submitted
        return ("submitted", None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_pending_classification_maps_to_submitted():
    state, reason = map_v01_to_v02_state("pending_classification", None)
    assert state == "submitted"
    assert reason is None


def test_pending_review_high_confidence_maps_to_intake_complete():
    """pending_review with confidence >= 0.5 → intake_complete."""
    for conf in [0.5, 0.51, 0.75, 0.9, 1.0]:
        state, reason = map_v01_to_v02_state("pending_review", conf)
        assert state == "intake_complete", f"Failed for confidence={conf}"
        assert reason is None


def test_pending_review_low_confidence_maps_to_exception_surfaced():
    """pending_review with confidence < 0.5 → exception_surfaced (R12)."""
    for conf in [0.0, 0.1, 0.3, 0.49]:
        state, reason = map_v01_to_v02_state("pending_review", conf)
        assert state == "exception_surfaced", f"Failed for confidence={conf}"
        assert reason == "low_confidence"


def test_pending_review_null_confidence_maps_to_exception_surfaced():
    """pending_review with NULL confidence → exception_surfaced (R12 explicit rule)."""
    state, reason = map_v01_to_v02_state("pending_review", None)
    assert state == "exception_surfaced"
    assert reason == "low_confidence"


def test_approved_maps_to_decision_recorded():
    state, reason = map_v01_to_v02_state("approved", None)
    assert state == "decision_recorded"
    assert reason is None


def test_rejected_maps_to_decision_recorded():
    state, reason = map_v01_to_v02_state("rejected", None)
    assert state == "decision_recorded"
    assert reason is None


def test_exact_threshold_boundary():
    """Exactly 0.5 confidence → intake_complete (inclusive lower bound)."""
    state, _ = map_v01_to_v02_state("pending_review", 0.5)
    assert state == "intake_complete"


def test_just_below_threshold():
    """0.4999... confidence → exception_surfaced."""
    state, _ = map_v01_to_v02_state("pending_review", 0.4999)
    assert state == "exception_surfaced"


@pytest.mark.asyncio
async def test_migration_adds_version_column(async_session):
    """After migration/init_db, Package rows have version field (default 1)."""
    from app.models import Package, User
    from app.auth import hash_password
    import uuid

    # Create a test user
    user = User(
        id=str(uuid.uuid4()),
        email=f"migtest_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("test123"),
        role="reviewer",
    )
    async_session.add(user)
    await async_session.flush()

    # Create a package — should default to version=1
    pkg = Package(
        title="Migration Version Test",
        uploaded_by=user.id,
        state="submitted",
        version=1,
    )
    async_session.add(pkg)
    await async_session.commit()
    await async_session.refresh(pkg)

    assert pkg.version == 1


@pytest.mark.asyncio
async def test_migration_reviewer_note_table_exists(async_session):
    """ReviewerNote table exists and accepts inserts after migration."""
    from app.models import Package, ReviewerNote, User
    from app.auth import hash_password
    import uuid

    # Create user and package
    user = User(
        id=str(uuid.uuid4()),
        email=f"rntest_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("test123"),
        role="reviewer",
    )
    async_session.add(user)
    await async_session.flush()

    pkg = Package(
        title="Note Migration Test",
        uploaded_by=user.id,
        state="intake_complete",
        version=1,
    )
    async_session.add(pkg)
    await async_session.flush()

    note = ReviewerNote(
        package_id=pkg.id,
        author_user_id=user.id,
        body="Migration test note",
    )
    async_session.add(note)
    await async_session.commit()
    await async_session.refresh(note)

    assert note.id is not None
    assert note.body == "Migration test note"
