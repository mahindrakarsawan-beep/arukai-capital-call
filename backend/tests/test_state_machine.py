"""TDD: State machine unit tests — all 36 transitions (9 allowed, 27 rejected).

Parametrized test of the full role × state matrix.
No DB. No async. Pure function tests.
Miller owns the larger contract test suite (Z1).
"""
import pytest
from app.state_machine import (
    DECISION_RECORDED,
    EXCEPTION_SURFACED,
    INTAKE_COMPLETE,
    ROUTED_FOR_APPROVAL,
    SUBMITTED,
    UNDER_REVIEW,
    ROLE_ADMIN,
    ROLE_APPROVER,
    ROLE_REVIEWER,
    ROLE_SYSTEM,
    InvalidTransition,
    InsufficientRole,
    is_terminal,
    next_owner,
    requires_claim,
    validate_transition,
)


# ---------------------------------------------------------------------------
# 9 ALLOWED transitions
# ---------------------------------------------------------------------------

ALLOWED_TRANSITIONS = [
    # (from, to, role, note_count, description)
    (SUBMITTED, INTAKE_COMPLETE, ROLE_SYSTEM, 0, "system: classify success"),
    (SUBMITTED, EXCEPTION_SURFACED, ROLE_SYSTEM, 0, "system: classify failure"),
    (INTAKE_COMPLETE, UNDER_REVIEW, ROLE_REVIEWER, 0, "reviewer: claim"),
    (INTAKE_COMPLETE, EXCEPTION_SURFACED, ROLE_REVIEWER, 0, "reviewer: flag exception"),
    (UNDER_REVIEW, ROUTED_FOR_APPROVAL, ROLE_REVIEWER, 0, "reviewer: route"),
    (UNDER_REVIEW, INTAKE_COMPLETE, ROLE_REVIEWER, 0, "reviewer: release (no notes)"),
    (UNDER_REVIEW, EXCEPTION_SURFACED, ROLE_REVIEWER, 0, "reviewer: escalate"),
    (ROUTED_FOR_APPROVAL, DECISION_RECORDED, ROLE_APPROVER, 0, "approver: attest"),
    (ROUTED_FOR_APPROVAL, UNDER_REVIEW, ROLE_APPROVER, 0, "approver: return for revision"),
    (EXCEPTION_SURFACED, INTAKE_COMPLETE, ROLE_ADMIN, 0, "admin: resolve exception"),
    (EXCEPTION_SURFACED, DECISION_RECORDED, ROLE_APPROVER, 0, "approver: reject from exception"),
]


@pytest.mark.parametrize("from_state,to_state,role,note_count,desc", ALLOWED_TRANSITIONS)
def test_allowed_transition(from_state, to_state, role, note_count, desc):
    """All allowed transitions must not raise."""
    validate_transition(from_state, to_state, role, note_count)  # should not raise


# ---------------------------------------------------------------------------
# Release-claim guard: note_count > 0 blocks under_review → intake_complete
# ---------------------------------------------------------------------------

def test_release_claim_blocked_when_notes_exist():
    """under_review → intake_complete must raise InvalidTransition when notes > 0 (R4)."""
    with pytest.raises(InvalidTransition) as exc_info:
        validate_transition(UNDER_REVIEW, INTAKE_COMPLETE, ROLE_REVIEWER, note_count=1)
    assert "cannot release claim after annotation" in str(exc_info.value)


def test_release_claim_allowed_when_no_notes():
    """under_review → intake_complete is allowed with zero notes."""
    validate_transition(UNDER_REVIEW, INTAKE_COMPLETE, ROLE_REVIEWER, note_count=0)


# ---------------------------------------------------------------------------
# 27 REJECTED transitions (wrong role)
# ---------------------------------------------------------------------------

WRONG_ROLE_TRANSITIONS = [
    # reviewer trying approver-only actions
    (ROUTED_FOR_APPROVAL, DECISION_RECORDED, ROLE_REVIEWER, "reviewer cannot attest"),
    (ROUTED_FOR_APPROVAL, UNDER_REVIEW, ROLE_REVIEWER, "reviewer cannot return for revision"),
    (EXCEPTION_SURFACED, DECISION_RECORDED, ROLE_REVIEWER, "reviewer cannot reject from exception"),

    # approver trying reviewer-only actions
    (INTAKE_COMPLETE, UNDER_REVIEW, ROLE_APPROVER, "approver cannot claim"),
    (INTAKE_COMPLETE, EXCEPTION_SURFACED, ROLE_APPROVER, "approver cannot flag"),
    (UNDER_REVIEW, ROUTED_FOR_APPROVAL, ROLE_APPROVER, "approver cannot route"),
    (UNDER_REVIEW, INTAKE_COMPLETE, ROLE_APPROVER, "approver cannot release claim"),
    (UNDER_REVIEW, EXCEPTION_SURFACED, ROLE_APPROVER, "approver cannot escalate"),

    # admin trying approver-only actions
    (ROUTED_FOR_APPROVAL, DECISION_RECORDED, ROLE_ADMIN, "admin cannot attest"),

    # reviewer trying admin-only actions
    (EXCEPTION_SURFACED, INTAKE_COMPLETE, ROLE_REVIEWER, "reviewer cannot resolve exception"),

    # approver trying admin-only actions
    (EXCEPTION_SURFACED, INTAKE_COMPLETE, ROLE_APPROVER, "approver cannot resolve exception"),

    # non-system trying system-only actions
    (SUBMITTED, INTAKE_COMPLETE, ROLE_REVIEWER, "reviewer cannot do system transition"),
    (SUBMITTED, INTAKE_COMPLETE, ROLE_APPROVER, "approver cannot do system transition"),
    (SUBMITTED, INTAKE_COMPLETE, ROLE_ADMIN, "admin cannot do system transition"),
    (SUBMITTED, EXCEPTION_SURFACED, ROLE_REVIEWER, "reviewer cannot do system exception"),
    (SUBMITTED, EXCEPTION_SURFACED, ROLE_APPROVER, "approver cannot do system exception"),
    (SUBMITTED, EXCEPTION_SURFACED, ROLE_ADMIN, "admin cannot do system exception"),
]


@pytest.mark.parametrize("from_state,to_state,role,desc", WRONG_ROLE_TRANSITIONS)
def test_wrong_role_rejected(from_state, to_state, role, desc):
    """Wrong-role transitions must raise InsufficientRole."""
    with pytest.raises(InsufficientRole):
        validate_transition(from_state, to_state, role)


# ---------------------------------------------------------------------------
# INVALID transitions (not in matrix at all)
# ---------------------------------------------------------------------------

INVALID_TRANSITIONS = [
    (SUBMITTED, UNDER_REVIEW, ROLE_REVIEWER, "submitted → under_review invalid"),
    (SUBMITTED, ROUTED_FOR_APPROVAL, ROLE_APPROVER, "submitted → routed_for_approval invalid"),
    (SUBMITTED, DECISION_RECORDED, ROLE_APPROVER, "submitted → decision_recorded invalid"),
    (INTAKE_COMPLETE, ROUTED_FOR_APPROVAL, ROLE_REVIEWER, "intake_complete → routed_for_approval invalid"),
    (INTAKE_COMPLETE, DECISION_RECORDED, ROLE_APPROVER, "intake_complete → decision_recorded invalid"),
    (INTAKE_COMPLETE, SUBMITTED, ROLE_ADMIN, "intake_complete → submitted invalid (no back)"),
    (UNDER_REVIEW, SUBMITTED, ROLE_ADMIN, "under_review → submitted invalid"),
    (UNDER_REVIEW, DECISION_RECORDED, ROLE_APPROVER, "under_review → decision_recorded invalid"),
    (ROUTED_FOR_APPROVAL, SUBMITTED, ROLE_ADMIN, "routed_for_approval → submitted invalid"),
    (ROUTED_FOR_APPROVAL, INTAKE_COMPLETE, ROLE_APPROVER, "routed_for_approval → intake_complete invalid"),
    (ROUTED_FOR_APPROVAL, EXCEPTION_SURFACED, ROLE_REVIEWER, "routed_for_approval → exception invalid"),
    (EXCEPTION_SURFACED, SUBMITTED, ROLE_ADMIN, "exception → submitted invalid"),
    (EXCEPTION_SURFACED, UNDER_REVIEW, ROLE_REVIEWER, "exception → under_review invalid"),
    (EXCEPTION_SURFACED, ROUTED_FOR_APPROVAL, ROLE_APPROVER, "exception → routed invalid"),
]


@pytest.mark.parametrize("from_state,to_state,role,desc", INVALID_TRANSITIONS)
def test_invalid_transition(from_state, to_state, role, desc):
    """Transitions not in the matrix must raise InvalidTransition."""
    with pytest.raises(InvalidTransition):
        validate_transition(from_state, to_state, role)


# ---------------------------------------------------------------------------
# Terminal state guard
# ---------------------------------------------------------------------------

def test_terminal_state_blocks_all_transitions():
    """decision_recorded is terminal — all transition attempts raise InvalidTransition."""
    for target in [SUBMITTED, INTAKE_COMPLETE, UNDER_REVIEW, ROUTED_FOR_APPROVAL, EXCEPTION_SURFACED]:
        for role in [ROLE_ADMIN, ROLE_REVIEWER, ROLE_APPROVER, ROLE_SYSTEM]:
            with pytest.raises(InvalidTransition) as exc_info:
                validate_transition(DECISION_RECORDED, target, role)
            assert "terminal" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

def test_is_terminal():
    assert is_terminal(DECISION_RECORDED) is True
    assert is_terminal(SUBMITTED) is False
    assert is_terminal(INTAKE_COMPLETE) is False
    assert is_terminal(UNDER_REVIEW) is False
    assert is_terminal(ROUTED_FOR_APPROVAL) is False
    assert is_terminal(EXCEPTION_SURFACED) is False


def test_next_owner_all_states():
    assert "system" in next_owner(SUBMITTED).lower()
    assert "reviewer" in next_owner(INTAKE_COMPLETE).lower()
    assert "reviewer" in next_owner(UNDER_REVIEW).lower()
    assert "With Alice" == next_owner(UNDER_REVIEW, reviewer_name="Alice")
    assert "approver" in next_owner(ROUTED_FOR_APPROVAL).lower()
    assert "recorded" in next_owner(DECISION_RECORDED).lower()
    assert "operator" in next_owner(EXCEPTION_SURFACED).lower()


def test_requires_claim():
    assert requires_claim(UNDER_REVIEW) is True
    assert requires_claim(ROUTED_FOR_APPROVAL) is True
    assert requires_claim(SUBMITTED) is False
    assert requires_claim(INTAKE_COMPLETE) is False
    assert requires_claim(DECISION_RECORDED) is False
    assert requires_claim(EXCEPTION_SURFACED) is False
