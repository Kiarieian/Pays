"""
Payment and disbursement state machines.

Validates that status transitions are always forward-moving.
A payment in a terminal state (SUCCESS, FAILED, TIMEOUT) cannot
accidentally transition backward to PENDING.
"""
import logging
from enum import Enum

logger = logging.getLogger("daraja.payments")


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class DisbursementStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


# Allowed transitions: current_state -> set of allowed next states
PAYMENT_TRANSITIONS: dict[str, set[str]] = {
    PaymentStatus.PENDING: {PaymentStatus.SUCCESS, PaymentStatus.FAILED, PaymentStatus.TIMEOUT},
    # Terminal states: no transitions allowed
    PaymentStatus.SUCCESS: set(),
    PaymentStatus.FAILED: set(),
    PaymentStatus.TIMEOUT: set(),
}

DISBURSEMENT_TRANSITIONS: dict[str, set[str]] = {
    DisbursementStatus.PENDING: {
        DisbursementStatus.SUCCESS,
        DisbursementStatus.FAILED,
        DisbursementStatus.TIMEOUT,
    },
    DisbursementStatus.SUCCESS: set(),
    DisbursementStatus.FAILED: set(),
    DisbursementStatus.TIMEOUT: set(),
}


def validate_payment_transition(current: str, new: str) -> bool:
    """Return True if the transition is valid, False otherwise."""
    allowed = PAYMENT_TRANSITIONS.get(current, set())
    if new not in allowed:
        logger.warning(
            "Invalid payment transition: %s -> %s (allowed: %s)",
            current, new, allowed or "none (terminal state)",
        )
        return False
    return True


def validate_disbursement_transition(current: str, new: str) -> bool:
    """Return True if the transition is valid, False otherwise."""
    allowed = DISBURSEMENT_TRANSITIONS.get(current, set())
    if new not in allowed:
        logger.warning(
            "Invalid disbursement transition: %s -> %s (allowed: %s)",
            current, new, allowed or "none (terminal state)",
        )
        return False
    return True
