"""Adversarial / security tests."""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch


class TestCrossTenantIsolation:
    def test_merchant_a_cannot_see_merchant_b_payments(self, client, db, test_merchant):
        from app.models import Payment
        from app.security import generate_api_key

        merchant_a, key_a = test_merchant

        # Create merchant B
        merchant_b = type(merchant_a)(
            business_name="Business B",
            email="b@example.com",
            phone="254733333333",
            status="active",
        )
        raw_key_b, prefix_b, hash_b = generate_api_key()
        merchant_b.api_key_prefix = prefix_b
        merchant_b.api_key_hash = hash_b
        db.add(merchant_b)
        db.commit()
        db.refresh(merchant_b)

        # Add payment for merchant B
        p = Payment(
            phone="254700000001",
            amount=999,
            merchant_id=merchant_b.id,
            checkout_request_id="ws_CO_B_ONLY",
        )
        db.add(p)
        db.commit()

        # Merchant A should NOT see merchant B's payment
        response = client.get("/payments", headers={"X-API-Key": key_a})
        assert response.status_code == 200
        for item in response.json():
            assert item["checkout_request_id"] != "ws_CO_B_ONLY"

    def test_merchant_cannot_activate_others(self, client, pending_merchant):
        _, raw_key = pending_merchant
        response = client.post(
            "/admin/merchants/activate",
            json={"merchant_id": 99999},
            headers={"X-Admin-Key": "wrong-key"},
        )
        assert response.status_code == 403


class TestInputValidation:
    def test_payment_negative_amount(self, client, test_merchant):
        _, raw_key = test_merchant
        response = client.post("/pay", json={
            "phone": "254712345678",
            "amount": -100,
        }, headers={"X-API-Key": raw_key})
        assert response.status_code == 422

    def test_payment_zero_amount(self, client, test_merchant):
        _, raw_key = test_merchant
        response = client.post("/pay", json={
            "phone": "254712345678",
            "amount": 0,
        }, headers={"X-API-Key": raw_key})
        assert response.status_code == 422

    def test_signup_malformed_email(self, client):
        response = client.post("/merchants/signup", json={
            "business_name": "X",
            "email": "not-an-email",
            "phone": "254712345678",
        })
        assert response.status_code == 422

    def test_missing_required_fields(self, client):
        response = client.post("/merchants/signup", json={})
        assert response.status_code == 422

    def test_empty_api_key(self, client):
        response = client.get("/merchants/me", headers={"X-API-Key": ""})
        assert response.status_code in (401, 422)


class TestAdminSecurity:
    def test_admin_endpoint_requires_key(self, client):
        response = client.post("/admin/merchants/activate", json={"merchant_id": 1})
        assert response.status_code == 422  # Missing X-Admin-Key header

    def test_admin_wrong_key(self, client):
        response = client.post(
            "/admin/merchants/activate",
            json={"merchant_id": 1},
            headers={"X-Admin-Key": "wrong"},
        )
        assert response.status_code == 403


class TestDuplicateRequestSafety:
    @patch("app.main.stk_push")
    def test_duplicate_initiation_different_keys(self, mock_stk, client, test_merchant):
        _, raw_key = test_merchant
        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_DIFF_123"}

        r1 = client.post("/pay", json={
            "phone": "254712345678",
            "amount": 100,
            "idempotency_key": "key-aaa",
        }, headers={"X-API-Key": raw_key})

        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_DIFF_456"}
        r2 = client.post("/pay", json={
            "phone": "254712345678",
            "amount": 100,
            "idempotency_key": "key-bbb",
        }, headers={"X-API-Key": raw_key})

        assert r1.status_code == 200
        assert r2.status_code == 200
        # Different idempotency keys => different payments
        assert r1.json()["payment_id"] != r2.json()["payment_id"]

    @patch("app.main.stk_push")
    def test_callback_does_not_revert_success(self, mock_stk, client, db, test_merchant):
        from app.models import Payment

        merchant, _ = test_merchant
        payment = Payment(
            phone="254712345678",
            amount=100,
            checkout_request_id="ws_CO_NO_REVERT",
            merchant_id=merchant.id,
            status="PENDING",
        )
        db.add(payment)
        db.commit()

        # Send success callback
        success_cb = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": "ws_CO_NO_REVERT",
                    "ResultCode": 0,
                    "CallbackMetadata": {
                        "Item": [{"Name": "MpesaReceiptNumber", "Value": "REC001"}]
                    },
                }
            }
        }
        client.post(
            f"/api/payment/callback/{merchant.id}",
            content=json.dumps(success_cb),
            headers={"Content-Type": "application/json"},
        )
        db.refresh(payment)
        assert payment.status == "SUCCESS"

        # Send failure callback for same payment — should NOT revert
        fail_cb = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": "ws_CO_NO_REVERT",
                    "ResultCode": 1032,
                }
            }
        }
        client.post(
            f"/api/payment/callback/{merchant.id}",
            content=json.dumps(fail_cb),
            headers={"Content-Type": "application/json"},
        )
        db.refresh(payment)
        assert payment.status == "SUCCESS"  # Still SUCCESS, not reverted
