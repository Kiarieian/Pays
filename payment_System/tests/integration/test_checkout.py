import os
import sys

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", "XIkBuofwH6Jk55CTrQ6ZeJwGmCWjRclh5stFnS0QQuU=")
os.environ.setdefault("ADMIN_SECRET", "test-admin-secret-key")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("PUBLIC_BASE_URL", "http://localhost:8000")

import pytest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models import Payment, PaymentLink


def _create_active_link(client, raw_key, amount=1500, description="Test checkout link"):
    resp = client.post(
        "/payment-links",
        json={"amount": amount, "description": description},
        headers={"X-API-Key": raw_key},
    )
    assert resp.status_code == 200
    return resp.json()["public_id"]


class TestPublicLinkView:
    """GET /pay/{public_id} — customer-facing link info."""

    def test_returns_link_details(self, client, test_merchant):
        merchant, raw_key = test_merchant
        public_id = _create_active_link(client, raw_key, amount=2500, description="Wedding")
        resp = client.get(f"/pay/{public_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["public_id"] == public_id
        assert data["amount"] == 2500
        assert data["currency"] == "KES"
        assert data["description"] == "Wedding"
        assert "merchant_id" not in data
        assert "id" not in data

    def test_no_auth_required(self, client, test_merchant):
        merchant, raw_key = test_merchant
        public_id = _create_active_link(client, raw_key)
        resp = client.get(f"/pay/{public_id}")
        assert resp.status_code == 200

    def test_returns_404_for_nonexistent(self, client):
        resp = client.get("/pay/doesnotexist")
        assert resp.status_code == 404

    def test_expired_link_returns_410(self, client, test_merchant):
        merchant, raw_key = test_merchant
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None)
        resp = client.post(
            "/payment-links",
            json={"amount": 1000, "expires_at": past.isoformat()},
            headers={"X-API-Key": raw_key},
        )
        public_id = resp.json()["public_id"]
        resp = client.get(f"/pay/{public_id}")
        assert resp.status_code == 410

    def test_disabled_link_returns_410(self, client, test_merchant):
        merchant, raw_key = test_merchant
        public_id = _create_active_link(client, raw_key)
        client.post(
            f"/payment-links/{public_id}/disable",
            headers={"X-API-Key": raw_key},
        )
        resp = client.get(f"/pay/{public_id}")
        assert resp.status_code == 410

    def test_paid_link_returns_200_with_paid_status(self, client, test_merchant, db):
        merchant, raw_key = test_merchant
        public_id = _create_active_link(client, raw_key)
        link = db.query(PaymentLink).filter(PaymentLink.public_id == public_id).first()
        link.status = "PAID"
        db.commit()
        resp = client.get(f"/pay/{public_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "PAID"


class TestPublicSTKPush:
    """POST /pay/{public_id}/stk — customer initiates payment."""

    @patch("app.main.stk_push")
    def test_stk_push_success(self, mock_stk, client, test_merchant):
        merchant, raw_key = test_merchant
        public_id = _create_active_link(client, raw_key, amount=1500)
        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_link_001"}

        resp = client.post(f"/pay/{public_id}/stk", json={"phone": "254712345678"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PENDING"
        assert data["message"] == "M-Pesa payment request sent to your phone."
        mock_stk.assert_called_once()

    @patch("app.main.stk_push")
    def test_stk_push_uses_link_amount_and_reference(self, mock_stk, client, test_merchant, db):
        merchant, raw_key = test_merchant
        public_id = _create_active_link(client, raw_key, amount=1500)
        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_link_002"}

        client.post(f"/pay/{public_id}/stk", json={"phone": "254712345678"})

        link = db.query(PaymentLink).filter(PaymentLink.public_id == public_id).first()
        call_args = mock_stk.call_args
        assert call_args[0][0] == merchant  # merchant object
        assert call_args[0][1] == "254712345678"  # phone
        assert call_args[0][2] == 1500  # amount from link
        assert call_args[0][3] == link.account_reference

    def test_stk_returns_404_for_nonexistent_link(self, client):
        resp = client.post("/pay/doesnotexist/stk", json={"phone": "254712345678"})
        assert resp.status_code == 404

    def test_stk_returns_410_for_expired_link(self, client, test_merchant):
        merchant, raw_key = test_merchant
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None)
        resp = client.post(
            "/payment-links",
            json={"amount": 1000, "expires_at": past.isoformat()},
            headers={"X-API-Key": raw_key},
        )
        public_id = resp.json()["public_id"]
        resp = client.post(f"/pay/{public_id}/stk", json={"phone": "254712345678"})
        assert resp.status_code == 410

    def test_stk_returns_409_for_already_paid_link(self, client, test_merchant, db):
        merchant, raw_key = test_merchant
        public_id = _create_active_link(client, raw_key)
        link = db.query(PaymentLink).filter(PaymentLink.public_id == public_id).first()
        link.status = "PAID"
        db.commit()
        resp = client.post(f"/pay/{public_id}/stk", json={"phone": "254712345678"})
        assert resp.status_code == 409

    def test_stk_returns_410_for_disabled_link(self, client, test_merchant):
        merchant, raw_key = test_merchant
        public_id = _create_active_link(client, raw_key)
        client.post(
            f"/payment-links/{public_id}/disable",
            headers={"X-API-Key": raw_key},
        )
        resp = client.post(f"/pay/{public_id}/stk", json={"phone": "254712345678"})
        assert resp.status_code == 410

    def test_stk_rejects_invalid_phone(self, client, test_merchant):
        merchant, raw_key = test_merchant
        public_id = _create_active_link(client, raw_key)
        resp = client.post(f"/pay/{public_id}/stk", json={"phone": "12345"})
        assert resp.status_code == 400

    @patch("app.main.stk_push")
    def test_stk_creates_linked_payment(self, mock_stk, client, test_merchant, db):
        merchant, raw_key = test_merchant
        public_id = _create_active_link(client, raw_key)
        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_link_003"}

        client.post(f"/pay/{public_id}/stk", json={"phone": "254712345678"})

        link = db.query(PaymentLink).filter(PaymentLink.public_id == public_id).first()
        payment = (
            db.query(Payment)
            .filter(Payment.payment_link_id == link.id)
            .first()
        )
        assert payment is not None
        assert payment.amount == link.amount
        assert payment.status == "PENDING"
        assert payment.checkout_request_id == "ws_CO_link_003"

    @patch("app.main.stk_push")
    def test_stk_idempotent_for_same_phone_and_link(self, mock_stk, client, test_merchant, db):
        merchant, raw_key = test_merchant
        public_id = _create_active_link(client, raw_key)
        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_link_004"}

        r1 = client.post(f"/pay/{public_id}/stk", json={"phone": "254712345678"})
        assert r1.status_code == 200

        r2 = client.post(f"/pay/{public_id}/stk", json={"phone": "254712345678"})
        assert r2.status_code == 200

        # Only one payment should be created
        link = db.query(PaymentLink).filter(PaymentLink.public_id == public_id).first()
        payments = db.query(Payment).filter(Payment.payment_link_id == link.id).all()
        assert len(payments) == 1

        # stk_push called only once
        assert mock_stk.call_count == 1

    @patch("app.main.stk_push")
    def test_stk_different_phones_create_separate_payments(self, mock_stk, client, test_merchant, db):
        merchant, raw_key = test_merchant
        public_id = _create_active_link(client, raw_key)
        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_link_005"}

        client.post(f"/pay/{public_id}/stk", json={"phone": "254712345678"})
        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_link_006"}
        client.post(f"/pay/{public_id}/stk", json={"phone": "254799999999"})

        link = db.query(PaymentLink).filter(PaymentLink.public_id == public_id).first()
        payments = db.query(Payment).filter(Payment.payment_link_id == link.id).all()
        assert len(payments) == 2

    @patch("app.main.stk_push")
    def test_stk_push_failure_returns_502(self, mock_stk, client, test_merchant):
        merchant, raw_key = test_merchant
        public_id = _create_active_link(client, raw_key)
        mock_stk.side_effect = Exception("Safaricom API timeout")

        resp = client.post(f"/pay/{public_id}/stk", json={"phone": "254712345678"})
        assert resp.status_code == 502
        assert "Safaricom API timeout" in resp.json()["detail"]


class TestPublicStatusEndpoint:
    """GET /pay/{public_id}/status — customer polls for payment result."""

    def test_returns_link_status_when_no_payments(self, client, test_merchant):
        merchant, raw_key = test_merchant
        public_id = _create_active_link(client, raw_key)
        resp = client.get(f"/pay/{public_id}/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ACTIVE"

    def test_no_auth_required(self, client, test_merchant):
        merchant, raw_key = test_merchant
        public_id = _create_active_link(client, raw_key)
        resp = client.get(f"/pay/{public_id}/status")
        assert resp.status_code == 200

    def test_returns_pending_payment_status(self, client, test_merchant, db):
        merchant, raw_key = test_merchant
        public_id = _create_active_link(client, raw_key)
        link = db.query(PaymentLink).filter(PaymentLink.public_id == public_id).first()
        payment = Payment(
            merchant_id=merchant.id,
            phone="254712345678",
            amount=1500,
            checkout_request_id="ws_CO_status_001",
            status="PENDING",
            payment_link_id=link.id,
        )
        db.add(payment)
        db.commit()

        resp = client.get(f"/pay/{public_id}/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "PENDING"

    def test_returns_success_with_receipt(self, client, test_merchant, db):
        merchant, raw_key = test_merchant
        public_id = _create_active_link(client, raw_key)
        link = db.query(PaymentLink).filter(PaymentLink.public_id == public_id).first()
        payment = Payment(
            merchant_id=merchant.id,
            phone="254712345678",
            amount=1500,
            checkout_request_id="ws_CO_status_002",
            status="SUCCESS",
            mpesa_receipt="QHJ4X5K8L9",
            payment_link_id=link.id,
        )
        db.add(payment)
        db.commit()

        resp = client.get(f"/pay/{public_id}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"
        assert data["receipt"] == "QHJ4X5K8L9"

    def test_returns_failed_status(self, client, test_merchant, db):
        merchant, raw_key = test_merchant
        public_id = _create_active_link(client, raw_key)
        link = db.query(PaymentLink).filter(PaymentLink.public_id == public_id).first()
        payment = Payment(
            merchant_id=merchant.id,
            phone="254712345678",
            amount=1500,
            checkout_request_id="ws_CO_status_003",
            status="FAILED",
            payment_link_id=link.id,
        )
        db.add(payment)
        db.commit()

        resp = client.get(f"/pay/{public_id}/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "FAILED"

    def test_returns_most_recent_payment(self, client, test_merchant, db):
        merchant, raw_key = test_merchant
        public_id = _create_active_link(client, raw_key)
        link = db.query(PaymentLink).filter(PaymentLink.public_id == public_id).first()

        old_payment = Payment(
            merchant_id=merchant.id,
            phone="254712345678",
            amount=1500,
            checkout_request_id="ws_CO_old",
            status="FAILED",
            payment_link_id=link.id,
        )
        db.add(old_payment)
        db.commit()

        new_payment = Payment(
            merchant_id=merchant.id,
            phone="254712345678",
            amount=1500,
            checkout_request_id="ws_CO_new",
            status="PENDING",
            payment_link_id=link.id,
        )
        db.add(new_payment)
        db.commit()

        # Force different created_at timestamps so ORDER BY works
        from sqlalchemy import text
        db.execute(text(
            f"UPDATE payments SET created_at = datetime('now', '-1 hour') "
            f"WHERE checkout_request_id = 'ws_CO_old'"
        ))
        db.commit()

        resp = client.get(f"/pay/{public_id}/status")
        assert resp.json()["status"] == "PENDING"

    def test_status_returns_404_for_nonexistent(self, client):
        resp = client.get("/pay/doesnotexist/status")
        assert resp.status_code == 404


class TestPaymentLinkTransitions:
    """Test PaymentLink status transitions after payment success."""

    @patch("app.main.stk_push")
    def test_successful_payment_marks_link_as_paid(self, mock_stk, client, test_merchant, db):
        from app.services.payment_service import update_transaction

        merchant, raw_key = test_merchant
        public_id = _create_active_link(client, raw_key, amount=1000)
        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_transition_001"}

        # Initiate STK
        client.post(f"/pay/{public_id}/stk", json={"phone": "254712345678"})

        link = db.query(PaymentLink).filter(PaymentLink.public_id == public_id).first()
        payment = (
            db.query(Payment)
            .filter(Payment.payment_link_id == link.id)
            .first()
        )

        # Simulate callback success
        update_transaction(db, payment.checkout_request_id, "SUCCESS", "QHJ4X5K8L9")

        db.refresh(link)
        assert link.status == "PAID"

        db.refresh(payment)
        assert payment.status == "SUCCESS"
        assert payment.mpesa_receipt == "QHJ4X5K8L9"

    def test_status_endpoint_returns_paid_after_callback(self, client, test_merchant, db):
        merchant, raw_key = test_merchant
        public_id = _create_active_link(client, raw_key)
        link = db.query(PaymentLink).filter(PaymentLink.public_id == public_id).first()
        link.status = "PAID"
        payment = Payment(
            merchant_id=merchant.id,
            phone="254712345678",
            amount=1500,
            checkout_request_id="ws_CO_done",
            status="SUCCESS",
            mpesa_receipt="ABCDEF1234",
            payment_link_id=link.id,
        )
        db.add(payment)
        db.commit()

        resp = client.get(f"/pay/{public_id}/status")
        assert resp.json()["status"] == "SUCCESS"
        assert resp.json()["receipt"] == "ABCDEF1234"

        resp = client.get(f"/pay/{public_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "PAID"
