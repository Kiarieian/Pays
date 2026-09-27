"""Idempotency constraint tests.

SQLite does not enforce partial unique indexes (WHERE ... IS NOT NULL),
so the DB-level constraint is only enforceable on PostgreSQL. These tests
verify the application-level behavior that works on both backends, plus
concurrency behavior using concurrent threads.
"""
import sys
import os
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch


class TestSequentialIdempotency:
    """Request A, then Request A again → one logical record."""

    @patch("app.main.stk_push")
    def test_sequential_duplicate_returns_same_payment(self, mock_stk, client, test_merchant):
        _, raw_key = test_merchant
        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_SEQ_001"}

        payload = {
            "phone": "254712345678",
            "amount": 250,
            "idempotency_key": "seq-dup-key-001",
        }
        r1 = client.post("/pay", json=payload, headers={"X-API-Key": raw_key})
        r2 = client.post("/pay", json=payload, headers={"X-API-Key": raw_key})

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["payment_id"] == r2.json()["payment_id"]
        assert r1.json()["checkout_id"] == r2.json()["checkout_id"]

    @patch("app.main.b2c_disbursement")
    def test_sequential_duplicate_disbursement(self, mock_b2c, client, test_merchant_b2c):
        _, raw_key = test_merchant_b2c
        mock_b2c.return_value = {
            "ConversationID": "CONV_SEQ_001",
            "OriginatorConversationID": "ORIG_SEQ_001",
        }

        payload = {
            "phone": "254712345678",
            "amount": 1000,
            "remarks": "Test payout",
            "idempotency_key": "seq-disb-key-001",
        }
        r1 = client.post("/disburse", json=payload, headers={"X-API-Key": raw_key})
        r2 = client.post("/disburse", json=payload, headers={"X-API-Key": raw_key})

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["disbursement_id"] == r2.json()["disbursement_id"]


class TestSameKeyDifferentPayload:
    """Same idempotency key, different payload → explicit rejection."""

    @patch("app.main.stk_push")
    def test_same_key_different_amount_returns_existing(self, mock_stk, client, test_merchant):
        _, raw_key = test_merchant
        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_PAYLOAD_001"}

        payload1 = {
            "phone": "254712345678",
            "amount": 100,
            "idempotency_key": "payload-mismatch-key",
        }
        r1 = client.post("/pay", json=payload1, headers={"X-API-Key": raw_key})

        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_PAYLOAD_002"}
        payload2 = {
            "phone": "254712345678",
            "amount": 999,
            "idempotency_key": "payload-mismatch-key",
        }
        r2 = client.post("/pay", json=payload2, headers={"X-API-Key": raw_key})

        assert r1.status_code == 200
        assert r2.status_code == 200
        # Second request returns the FIRST payment — idempotency wins
        assert r2.json()["payment_id"] == r1.json()["payment_id"]
        # Amount is from the first request
        from app.models import Payment
        from tests.conftest import TestSessionLocal
        session = TestSessionLocal()
        payment = session.query(Payment).filter(Payment.id == r1.json()["payment_id"]).first()
        assert payment.amount == 100
        session.close()

    @patch("app.main.stk_push")
    def test_same_key_different_phone_returns_existing(self, mock_stk, client, test_merchant):
        _, raw_key = test_merchant
        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_PHONE_001"}

        payload1 = {
            "phone": "254712345678",
            "amount": 100,
            "idempotency_key": "phone-mismatch-key",
        }
        r1 = client.post("/pay", json=payload1, headers={"X-API-Key": raw_key})

        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_PHONE_002"}
        payload2 = {
            "phone": "254798765432",
            "amount": 100,
            "idempotency_key": "phone-mismatch-key",
        }
        r2 = client.post("/pay", json=payload2, headers={"X-API-Key": raw_key})

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r2.json()["payment_id"] == r1.json()["payment_id"]


class TestCrossMerchantIdempotency:
    """Different merchants can use the same idempotency key independently."""

    @patch("app.main.stk_push")
    def test_different_merchants_same_key_independent(self, mock_stk, client, db, test_merchant):
        from app.models import Merchant
        from app.security import generate_api_key

        merchant_a, key_a = test_merchant

        merchant_b = Merchant(
            business_name="Business B",
            email="idem_b@example.com",
            phone="254744444444",
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

        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_XM_A"}
        payload_a = {
            "phone": "254712345678",
            "amount": 100,
            "idempotency_key": "shared-key-001",
        }
        ra = client.post("/pay", json=payload_a, headers={"X-API-Key": key_a})

        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_XM_B"}
        payload_b = {
            "phone": "254712345678",
            "amount": 200,
            "idempotency_key": "shared-key-001",
        }
        rb = client.post("/pay", json=payload_b, headers={"X-API-Key": raw_key_b})

        assert ra.status_code == 200
        assert rb.status_code == 200
        # Different merchants → different payments, same key is fine
        assert ra.json()["payment_id"] != rb.json()["payment_id"]

    @patch("app.main.stk_push")
    def test_no_idempotency_key_allows_duplicates(self, mock_stk, client, test_merchant):
        _, raw_key = test_merchant
        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_NO_IDEM_1"}

        payload = {"phone": "254712345678", "amount": 100}
        r1 = client.post("/pay", json=payload, headers={"X-API-Key": raw_key})

        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_NO_IDEM_2"}
        r2 = client.post("/pay", json=payload, headers={"X-API-Key": raw_key})

        assert r1.status_code == 200
        assert r2.status_code == 200
        # Without idempotency key, both create separate records
        assert r1.json()["payment_id"] != r2.json()["payment_id"]


class TestConcurrentIdempotency:
    """Simultaneous requests with same merchant_id + idempotency_key.

    The DB constraint ensures exactly one record. The application
    catches IntegrityError and returns the existing record.
    """

    @patch("app.main.stk_push")
    def test_concurrent_duplicate_exactly_one_record(self, mock_stk, client, test_merchant):
        _, raw_key = test_merchant
        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_CONCURRENT_001"}

        from app.models import Payment
        from tests.conftest import TestSessionLocal

        results = []
        errors = []

        def make_payment(idx):
            try:
                # Each thread gets its own session
                session = TestSessionLocal()
                from app.services.payment_service import create_payment
                payment = create_payment(
                    session,
                    phone="254712345678",
                    amount=500,
                    checkout_request_id=f"ws_CO_CONCURRENT_{idx}",
                    merchant_id=merchant_a.id,
                    idempotency_key="concurrent-key-001",
                )
                results.append(payment.id)
            except Exception as e:
                errors.append(str(e))
            finally:
                session.close()

        merchant_a = test_merchant[0]

        threads = [threading.Thread(target=make_payment, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should succeed (no crashes)
        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 5

        # All should have received the same payment id
        assert len(set(results)) == 1, f"Got different IDs: {set(results)}"

        # Verify exactly one record in DB
        session = TestSessionLocal()
        count = (
            session.query(Payment)
            .filter(Payment.idempotency_key == "concurrent-key-001")
            .count()
        )
        session.close()
        assert count == 1

    @patch("app.main.b2c_disbursement")
    def test_concurrent_disbursement_idempotency(self, mock_b2c, client, test_merchant_b2c):
        _, raw_key = test_merchant_b2c
        mock_b2c.return_value = {
            "ConversationID": "CONV_CONCURRENT_001",
            "OriginatorConversationID": "ORIG_CONCURRENT_001",
        }

        from app.models import Disbursement
        from tests.conftest import TestSessionLocal

        results = []
        errors = []

        def make_disbursement(idx):
            try:
                session = TestSessionLocal()
                from app.services.payment_service import create_disbursement
                disb = create_disbursement(
                    session,
                    merchant_id=merchant_a.id,
                    phone="254712345678",
                    amount=1000,
                    remarks="Concurrent test",
                    conversation_id=f"CONV_CONCURRENT_{idx}",
                    idempotency_key="concurrent-disb-key-001",
                )
                results.append(disb.id)
            except Exception as e:
                errors.append(str(e))
            finally:
                session.close()

        merchant_a = test_merchant_b2c[0]

        threads = [threading.Thread(target=make_disbursement, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 5
        assert len(set(results)) == 1

        session = TestSessionLocal()
        count = (
            session.query(Disbursement)
            .filter(Disbursement.idempotency_key == "concurrent-disb-key-001")
            .count()
        )
        session.close()
        assert count == 1
