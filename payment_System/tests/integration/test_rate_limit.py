"""Rate limiting tests."""
import hashlib
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch


def _api_key_hash(api_key: str) -> str:
    """Compute the rate limit key hash from an API key."""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


class TestPaymentRateLimit:
    """Payment endpoint: 10 requests per minute per merchant (by API key)."""

    @patch("app.main.stk_push")
    def test_below_limit_allowed(self, mock_stk, client, test_merchant):
        _, raw_key = test_merchant
        mock_stk.side_effect = [
            {"CheckoutRequestID": f"ws_CO_RL_{i}"} for i in range(10)
        ]

        for i in range(10):
            r = client.post("/pay", json={
                "phone": "254712345678",
                "amount": 10,
                "idempotency_key": f"rl-pay-{i}",
            }, headers={"X-API-Key": raw_key})
            assert r.status_code == 200, f"Request {i+1} should succeed"

    @patch("app.main.stk_push")
    def test_above_limit_rejected(self, mock_stk, client, test_merchant):
        from app.rate_limit import payment_limiter
        _, raw_key = test_merchant
        key = f"pay:{_api_key_hash(raw_key)}"
        payment_limiter.reset(key)

        mock_stk.side_effect = [
            {"CheckoutRequestID": f"ws_CO_RLO_{i}"} for i in range(10)
        ]

        for i in range(10):
            client.post("/pay", json={
                "phone": "254712345678",
                "amount": 10,
                "idempotency_key": f"rl-pay-over-{i}",
            }, headers={"X-API-Key": raw_key})

        r = client.post("/pay", json={
            "phone": "254712345678",
            "amount": 10,
            "idempotency_key": "rl-pay-over-overflow",
        }, headers={"X-API-Key": raw_key})
        assert r.status_code == 429
        assert "Rate limit" in r.json()["detail"]

    @patch("app.main.stk_push")
    def test_window_reset_allows_again(self, mock_stk, client, test_merchant):
        from app.rate_limit import payment_limiter
        _, raw_key = test_merchant
        key = f"pay:{_api_key_hash(raw_key)}"
        payment_limiter.reset(key)

        mock_stk.side_effect = [
            {"CheckoutRequestID": f"ws_CO_RLR_{i}"} for i in range(10)
        ]

        for i in range(10):
            client.post("/pay", json={
                "phone": "254712345678",
                "amount": 10,
                "idempotency_key": f"rl-reset-{i}",
            }, headers={"X-API-Key": raw_key})

        r = client.post("/pay", json={
            "phone": "254712345678",
            "amount": 10,
            "idempotency_key": "rl-reset-blocked",
        }, headers={"X-API-Key": raw_key})
        assert r.status_code == 429

        payment_limiter.reset(key)

        mock_stk.side_effect = [{"CheckoutRequestID": "ws_CO_RLR_AFTER"}]
        r = client.post("/pay", json={
            "phone": "254712345678",
            "amount": 10,
            "idempotency_key": "rl-reset-after",
        }, headers={"X-API-Key": raw_key})
        assert r.status_code == 200


class TestCrossMerchantIsolation:
    """Merchant A's usage cannot consume Merchant B's quota."""

    @patch("app.main.stk_push")
    def test_merchants_have_independent_quotas(self, mock_stk, client, db, test_merchant):
        from app.rate_limit import payment_limiter
        from app.models import Merchant
        from app.security import generate_api_key

        merchant_a, key_a = test_merchant
        payment_limiter.reset(f"pay:{_api_key_hash(key_a)}")

        merchant_b = Merchant(
            business_name="Business B",
            email="rl_b@example.com",
            phone="254755555555",
            status="active",
        )
        raw_key_b, prefix_b, hash_b = generate_api_key()
        merchant_b.api_key_prefix = prefix_b
        merchant_b.api_key_hash = hash_b
        merchant_b.set_daraja_credentials(
            consumer_key="ck", consumer_secret="cs",
            passkey="pk", shortcode="174379",
            callback_base_url="https://example.com", environment="sandbox",
        )
        db.add(merchant_b)
        db.commit()
        db.refresh(merchant_b)
        payment_limiter.reset(f"pay:{_api_key_hash(raw_key_b)}")

        mock_stk.side_effect = [
            {"CheckoutRequestID": f"ws_CO_XM_A_{i}"} for i in range(5)
        ]
        for i in range(5):
            client.post("/pay", json={
                "phone": "254712345678",
                "amount": 10,
                "idempotency_key": f"xm-a-{i}",
            }, headers={"X-API-Key": key_a})

        mock_stk.side_effect = [
            {"CheckoutRequestID": f"ws_CO_XM_B_{i}"} for i in range(10)
        ]
        for i in range(10):
            r = client.post("/pay", json={
                "phone": "254712345678",
                "amount": 10,
                "idempotency_key": f"xm-b-{i}",
            }, headers={"X-API-Key": raw_key_b})
            assert r.status_code == 200, f"Merchant B request {i+1} should succeed"


class TestDisbursementRateLimit:
    """Disbursement: 5 requests per minute per merchant (by API key)."""

    @patch("app.main.b2c_disbursement")
    def test_disbursement_limit(self, mock_b2c, client, test_merchant_b2c):
        from app.rate_limit import disbursement_limiter
        _, raw_key = test_merchant_b2c
        key = f"disb:{_api_key_hash(raw_key)}"
        disbursement_limiter.reset(key)

        mock_b2c.side_effect = [
            {"ConversationID": f"CONV_RL_{i}", "OriginatorConversationID": f"ORIG_RL_{i}"}
            for i in range(5)
        ]

        for i in range(5):
            r = client.post("/disburse", json={
                "phone": "254712345678",
                "amount": 100,
                "idempotency_key": f"rl-disb-{i}",
            }, headers={"X-API-Key": raw_key})
            assert r.status_code == 200

        r = client.post("/disburse", json={
            "phone": "254712345678",
            "amount": 100,
            "idempotency_key": "rl-disb-overflow",
        }, headers={"X-API-Key": raw_key})
        assert r.status_code == 429


class TestAdminRateLimit:
    """Admin endpoints: 20 requests per minute per IP."""

    def test_admin_limit(self, client, pending_merchant):
        from app.rate_limit import admin_limiter
        admin_limiter.reset("admin:testclient")

        merchant, _ = pending_merchant
        for i in range(20):
            r = client.post("/admin/merchants/activate", json={
                "merchant_id": merchant.id,
            }, headers={"X-Admin-Key": "wrong-key"})
            assert r.status_code == 403, f"Request {i+1}: expected 403, got {r.status_code}"

        r = client.post("/admin/merchants/activate", json={
            "merchant_id": merchant.id,
        }, headers={"X-Admin-Key": "wrong-key"})
        assert r.status_code == 429


class TestRateLimitHeaders:
    """Verify rate limit headers are returned."""

    @patch("app.main.stk_push")
    def test_rate_limit_headers_present(self, mock_stk, client, test_merchant):
        _, raw_key = test_merchant
        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_HDR"}

        r = client.post("/pay", json={
            "phone": "254712345678",
            "amount": 10,
            "idempotency_key": "header-test",
        }, headers={"X-API-Key": raw_key})

        assert "X-RateLimit-Limit" in r.headers
        assert "X-RateLimit-Remaining" in r.headers
        assert int(r.headers["X-RateLimit-Limit"]) > 0


class TestCallbackNotRateLimited:
    """Safaricom callbacks must never be rate limited."""

    def test_callback_bypasses_rate_limit(self, client, db, test_merchant):
        from app.models import Payment

        merchant, _ = test_merchant
        payment = Payment(
            phone="254712345678",
            amount=100,
            checkout_request_id="ws_CO_CB_RL",
            merchant_id=merchant.id,
            status="PENDING",
        )
        db.add(payment)
        db.commit()

        cb = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": "ws_CO_CB_RL",
                    "ResultCode": 0,
                    "CallbackMetadata": {
                        "Item": [{"Name": "MpesaReceiptNumber", "Value": "CBRL001"}]
                    },
                }
            }
        }

        for _ in range(20):
            r = client.post(
                f"/api/payment/callback/{merchant.id}",
                content=__import__("json").dumps(cb),
                headers={"Content-Type": "application/json"},
            )
            assert r.status_code == 200
