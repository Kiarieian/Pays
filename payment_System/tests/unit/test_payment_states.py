"""Unit tests for payment state machine."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.payment_states import (
    PaymentStatus,
    DisbursementStatus,
    validate_payment_transition,
    validate_disbursement_transition,
)


class TestPaymentTransitions:
    def test_pending_to_success(self):
        assert validate_payment_transition("PENDING", "SUCCESS") is True

    def test_pending_to_failed(self):
        assert validate_payment_transition("PENDING", "FAILED") is True

    def test_pending_to_timeout(self):
        assert validate_payment_transition("PENDING", "TIMEOUT") is True

    def test_success_is_terminal(self):
        assert validate_payment_transition("SUCCESS", "PENDING") is False
        assert validate_payment_transition("SUCCESS", "FAILED") is False

    def test_failed_is_terminal(self):
        assert validate_payment_transition("FAILED", "PENDING") is False
        assert validate_payment_transition("FAILED", "SUCCESS") is False

    def test_timeout_is_terminal(self):
        assert validate_payment_transition("TIMEOUT", "PENDING") is False
        assert validate_payment_transition("TIMEOUT", "SUCCESS") is False

    def test_invalid_status(self):
        assert validate_payment_transition("UNKNOWN", "SUCCESS") is False


class TestDisbursementTransitions:
    def test_pending_to_success(self):
        assert validate_disbursement_transition("PENDING", "SUCCESS") is True

    def test_pending_to_failed(self):
        assert validate_disbursement_transition("PENDING", "FAILED") is True

    def test_pending_to_timeout(self):
        assert validate_disbursement_transition("PENDING", "TIMEOUT") is True

    def test_success_is_terminal(self):
        assert validate_disbursement_transition("SUCCESS", "PENDING") is False

    def test_failed_is_terminal(self):
        assert validate_disbursement_transition("FAILED", "PENDING") is False

    def test_timeout_is_terminal(self):
        assert validate_disbursement_transition("TIMEOUT", "PENDING") is False
