"""Integration tests for API endpoints."""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_home_returns_message(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "message" in response.json()


class TestMerchantSignup:
    def test_signup_success(self, client):
        response = client.post("/merchants/signup", json={
            "business_name": "New Business",
            "email": "new@example.com",
            "phone": "254799999999",
        })
        assert response.status_code == 200
        data = response.json()
        assert "merchant_id" in data
        assert data["status"] == "pending"
        assert "api_key" in data
        assert data["api_key"].startswith("sk_live_")

    def test_signup_duplicate_email(self, client, test_merchant):
        merchant, _ = test_merchant
        response = client.post("/merchants/signup", json={
            "business_name": "Another Business",
            "email": merchant.email,
            "phone": "254788888888",
        })
        assert response.status_code == 409


class TestMerchantProfile:
    def test_get_profile(self, client, test_merchant):
        _, raw_key = test_merchant
        response = client.get("/merchants/me", headers={"X-API-Key": raw_key})
        assert response.status_code == 200
        data = response.json()
        assert data["business_name"] == "Test Business"
        assert data["status"] == "active"

    def test_get_profile_no_key(self, client):
        response = client.get("/merchants/me")
        assert response.status_code == 401

    def test_get_profile_invalid_key(self, client):
        response = client.get("/merchants/me", headers={"X-API-Key": "sk_live_invalidkey"})
        assert response.status_code == 401

    def test_pending_merchant_forbidden(self, client, pending_merchant):
        _, raw_key = pending_merchant
        response = client.get("/merchants/me", headers={"X-API-Key": raw_key})
        assert response.status_code == 403


class TestAdminActivation:
    def test_activate_merchant(self, client, pending_merchant):
        merchant, _ = pending_merchant
        response = client.post("/admin/merchants/activate", json={
            "merchant_id": merchant.id,
        }, headers={"X-Admin-Key": "test-admin-secret-key"})
        assert response.status_code == 200
        assert response.json()["status"] == "active"

    def test_activate_invalid_admin_key(self, client, pending_merchant):
        merchant, _ = pending_merchant
        response = client.post("/admin/merchants/activate", json={
            "merchant_id": merchant.id,
        }, headers={"X-Admin-Key": "wrong-key"})
        assert response.status_code == 403


class TestPayments:
    @patch("app.main.stk_push")
    def test_pay_success(self, mock_stk, client, test_merchant):
        _, raw_key = test_merchant
        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_12345"}

        response = client.post("/pay", json={
            "phone": "254712345678",
            "amount": 100,
        }, headers={"X-API-Key": raw_key})
        assert response.status_code == 200
        data = response.json()
        assert data["checkout_id"] == "ws_CO_12345"
        assert data["status"] == "PENDING"

    def test_pay_no_daraja_credentials(self, client, db):
        from app.models import Merchant
        from app.security import generate_api_key

        merchant = Merchant(
            business_name="No Creds",
            email="nocreds@example.com",
            phone="254755555555",
            status="active",
        )
        raw_key, prefix, h = generate_api_key()
        merchant.api_key_prefix = prefix
        merchant.api_key_hash = h
        db.add(merchant)
        db.commit()

        response = client.post("/pay", json={
            "phone": "254712345678",
            "amount": 100,
        }, headers={"X-API-Key": raw_key})
        assert response.status_code == 400

    def test_pay_invalid_phone(self, client, test_merchant):
        _, raw_key = test_merchant
        response = client.post("/pay", json={
            "phone": "12345",
            "amount": 100,
        }, headers={"X-API-Key": raw_key})
        assert response.status_code == 400

    @patch("app.main.stk_push")
    def test_pay_idempotency(self, mock_stk, client, test_merchant):
        _, raw_key = test_merchant
        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_idem123"}

        payload = {
            "phone": "254712345678",
            "amount": 500,
            "idempotency_key": "unique-key-001",
        }
        r1 = client.post("/pay", json=payload, headers={"X-API-Key": raw_key})
        r2 = client.post("/pay", json=payload, headers={"X-API-Key": raw_key})
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["payment_id"] == r2.json()["payment_id"]


class TestCallbacks:
    def test_stk_callback_success(self, client, db, test_merchant):
        from app.models import Payment

        merchant, _ = test_merchant
        payment = Payment(
            phone="254712345678",
            amount=100,
            checkout_request_id="ws_CO_CALLBACK_TEST",
            merchant_id=merchant.id,
            status="PENDING",
        )
        db.add(payment)
        db.commit()

        callback_payload = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": "ws_CO_CALLBACK_TEST",
                    "ResultCode": 0,
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "MpesaReceiptNumber", "Value": "QHK3F12345"}
                        ]
                    },
                }
            }
        }
        response = client.post(
            f"/api/payment/callback/{merchant.id}",
            content=json.dumps(callback_payload),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200
        assert response.json()["ResultCode"] == 0

        db.refresh(payment)
        assert payment.status == "SUCCESS"
        assert payment.mpesa_receipt == "QHK3F12345"

    def test_stk_callback_failure(self, client, db, test_merchant):
        from app.models import Payment

        merchant, _ = test_merchant
        payment = Payment(
            phone="254712345678",
            amount=100,
            checkout_request_id="ws_CO_FAIL_TEST",
            merchant_id=merchant.id,
            status="PENDING",
        )
        db.add(payment)
        db.commit()

        callback_payload = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": "ws_CO_FAIL_TEST",
                    "ResultCode": 1032,
                }
            }
        }
        response = client.post(
            f"/api/payment/callback/{merchant.id}",
            content=json.dumps(callback_payload),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200

        db.refresh(payment)
        assert payment.status == "FAILED"

    def test_stk_callback_duplicate(self, client, db, test_merchant):
        from app.models import Payment

        merchant, _ = test_merchant
        payment = Payment(
            phone="254712345678",
            amount=100,
            checkout_request_id="ws_CO_DUP_TEST",
            merchant_id=merchant.id,
            status="PENDING",
        )
        db.add(payment)
        db.commit()

        callback_payload = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": "ws_CO_DUP_TEST",
                    "ResultCode": 0,
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "MpesaReceiptNumber", "Value": "QHK3F99999"}
                        ]
                    },
                }
            }
        }
        r1 = client.post(
            f"/api/payment/callback/{merchant.id}",
            content=json.dumps(callback_payload),
            headers={"Content-Type": "application/json"},
        )
        r2 = client.post(
            f"/api/payment/callback/{merchant.id}",
            content=json.dumps(callback_payload),
            headers={"Content-Type": "application/json"},
        )
        assert r1.status_code == 200
        assert r2.status_code == 200

        db.refresh(payment)
        assert payment.status == "SUCCESS"

    def test_stk_callback_unknown_checkout(self, client, db, test_merchant):
        merchant, _ = test_merchant
        callback_payload = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": "ws_CO_UNKNOWN",
                    "ResultCode": 0,
                }
            }
        }
        response = client.post(
            f"/api/payment/callback/{merchant.id}",
            content=json.dumps(callback_payload),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200


class TestGetPayments:
    def test_list_payments(self, client, db, test_merchant):
        from app.models import Payment

        merchant, _ = test_merchant
        for i in range(3):
            p = Payment(
                phone=f"25471000000{i}",
                amount=100 * (i + 1),
                merchant_id=merchant.id,
                checkout_request_id=f"ws_CO_LIST_{i}",
            )
            db.add(p)
        db.commit()

        response = client.get("/payments", headers={"X-API-Key": test_merchant[1]})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_payments_scoped_to_merchant(self, client, db, test_merchant):
        from app.models import Payment

        merchant, raw_key = test_merchant
        other = client.post("/merchants/signup", json={
            "business_name": "Other",
            "email": "other@example.com",
            "phone": "254760000000",
        }).json()
        # other merchant payments should not appear

        p = Payment(
            phone="254710000000",
            amount=500,
            merchant_id=merchant.id,
            checkout_request_id="ws_CO_MINE",
        )
        db.add(p)
        db.commit()

        response = client.get("/payments", headers={"X-API-Key": raw_key})
        assert response.status_code == 200
        for item in response.json():
            assert item["checkout_request_id"] == "ws_CO_MINE"
