"""Pure state machine for Arukai Capital Call v0.2 (POR-147 / ARU-17-B1).

No DB. No async. Fully unit-testable by Miller.

6 states, role × state transition matrix, optimistic locking support.
"""
from typing import Optional


# ---------------------------------------------------------------------------
# State constants
# ---------------------------------------------------------------------------

SUBMITTED = "submitted"
INTAKE_COMPLETE = "intake_complete"
UNDER_REVIEW = "under_review"
ROUTED_FOR_APPROVAL = "routed_for_approval"
DECISION_RECORDED = "decision_recorded"
EXCEPTION_SURFACED = "exception_surfaced"

ALL_STATES = {
    SUBMITTED,
    INTAKE_COMPLETE,
    UNDER_REVIEW,
    ROUTED_FOR_APPROVAL,
    DECISION_RECORDED,
    EXCEPTION_SURFACED,
}

TERMINAL_STATES = {DECISION_RECORDED}

# ---------------------------------------------------------------------------
# Role constants
# ---------------------------------------------------------------------------

ROLE_ADMIN = "admin"      # operator in UI
ROLE_REVIEWER = "reviewer"
ROLE_APPROVER = "approver"
ROLE_SYSTEM = "system"    # internal only — not user-callable

ALL_ROLES = {ROLE_ADMIN, ROLE_REVIEWER, ROLE_APPROVER, ROLE_SYSTEM}

# ---------------------------------------------------------------------------
# Transition matrix
# {(from_state, to_state): {roles that may perform this transition}}
# ---------------------------------------------------------------------------
#
# Per spec §2.2:
#   submitted → intake_complete         system only
#   submitted → exception_surfaced      system only
#   intake_complete → under_review      reviewer (claim or first note)
#   intake_complete → exception_surfaced reviewer (flag)
#   under_review → routed_for_approval  reviewer (route)
#   under_review → intake_complete      reviewer (release claim — only if no notes)
#   under_review → exception_surfaced   reviewer (escalate)
#   routed_for_approval → decision_recorded  approver (via /attest)
#   routed_for_approval → under_review  approver (return for revision)
#   exception_surfaced → intake_complete     admin/operator (resolve)
#   exception_surfaced → decision_recorded   approver (reject directly)
#   decision_recorded → (terminal)

TRANSITION_PERMISSIONS: dict[tuple[str, str], frozenset[str]] = {
    (SUBMITTED, INTAKE_COMPLETE): frozenset({ROLE_SYSTEM}),
    (SUBMITTED, EXCEPTION_SURFACED): frozenset({ROLE_SYSTEM}),

    (INTAKE_COMPLETE, UNDER_REVIEW): frozenset({ROLE_REVIEWER}),
    (INTAKE_COMPLETE, EXCEPTION_SURFACED): frozenset({ROLE_REVIEWER}),

    (UNDER_REVIEW, ROUTED_FOR_APPROVAL): frozenset({ROLE_REVIEWER}),
    (UNDER_REVIEW, INTAKE_COMPLETE): frozenset({ROLE_REVIEWER}),
    (UNDER_REVIEW, EXCEPTION_SURFACED): frozenset({ROLE_REVIEWER}),

    (ROUTED_FOR_APPROVAL, DECISION_RECORDED): frozenset({ROLE_APPROVER}),
    (ROUTED_FOR_APPROVAL, UNDER_REVIEW): frozenset({ROLE_APPROVER}),

    (EXCEPTION_SURFACED, INTAKE_COMPLETE): frozenset({ROLE_ADMIN}),
    (EXCEPTION_SURFACED, DECISION_RECORDED): frozenset({ROLE_APPROVER}),
}

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class InvalidTransition(Exception):
    """Raised when the requested state transition is not permitted."""

    def __init__(self, from_state: str, to_state: str, reason: Optional[str] = None) -> None:
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        msg = f"Transition {from_state}→{to_state} not permitted"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class InsufficientRole(Exception):
    """Raised when the actor's role may not perform the requested transition."""

    def __init__(self, from_state: str, to_state: str, actor_role: str) -> None:
        self.from_state = from_state
        self.to_state = to_state
        self.actor_role = actor_role
        super().__init__(
            f"Role '{actor_role}' may not transition {from_state}→{to_state}. "
            f"This action is outside your workflow role."
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_transition(
    from_state: str,
    to_state: str,
    actor_role: str,
    note_count: int = 0,
) -> None:
    """Validate a requested state transition.

    Args:
        from_state:  Current package state.
        to_state:    Requested next state.
        actor_role:  Role of the requesting user (admin/reviewer/approver/system).
        note_count:  Number of ReviewerNote rows for this package (used to guard
                     under_review → intake_complete per spec §2.2).

    Raises:
        InvalidTransition: Transition is not in the allowed matrix, or business
                           rule (e.g. note_count > 0) blocks it.
        InsufficientRole:  Transition is valid in the matrix but the actor role
                           is not permitted to perform it.
    """
    # Terminal state — no transitions ever allowed
    if from_state in TERMINAL_STATES:
        raise InvalidTransition(from_state, to_state, "package is in terminal state")

    # Check the transition exists in the matrix
    key = (from_state, to_state)
    if key not in TRANSITION_PERMISSIONS:
        raise InvalidTransition(from_state, to_state)

    # Check role permission
    allowed_roles = TRANSITION_PERMISSIONS[key]
    if actor_role not in allowed_roles:
        raise InsufficientRole(from_state, to_state, actor_role)

    # Business-rule guard: reviewer cannot release claim once notes have been recorded
    if from_state == UNDER_REVIEW and to_state == INTAKE_COMPLETE and note_count > 0:
        raise InvalidTransition(
            from_state,
            to_state,
            "cannot release claim after annotation — notes are recorded",
        )


def is_terminal(state: str) -> bool:
    """Return True if the state is terminal (no further transitions allowed)."""
    return state in TERMINAL_STATES


def next_owner(state: str, reviewer_name: Optional[str] = None) -> str:
    """Compute the next-owner chip text for a given state (per spec §3).

    Args:
        state: Package state string.
        reviewer_name: Reviewer name when under_review and claimed.

    Returns:
        Human-readable next-owner string.
    """
    if state == SUBMITTED:
        return "Awaiting system intake"
    if state == INTAKE_COMPLETE:
        return "Awaiting reviewer"
    if state == UNDER_REVIEW:
        if reviewer_name:
            return f"With {reviewer_name}"
        return "Awaiting reviewer"
    if state == ROUTED_FOR_APPROVAL:
        return "Awaiting approver attestation"
    if state == DECISION_RECORDED:
        return "Decision recorded"
    if state == EXCEPTION_SURFACED:
        return "Awaiting operator"
    return "Unknown"


def requires_claim(state: str) -> bool:
    """Return True if the state requires a claim record to be present."""
    return state in {UNDER_REVIEW, ROUTED_FOR_APPROVAL}
