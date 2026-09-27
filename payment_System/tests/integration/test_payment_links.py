import os
import sys

# Must be set before any app module imports
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", "XIkBuofwH6Jk55CTrQ6ZeJwGmCWjRclh5stFnS0QQuU=")
os.environ.setdefault("ADMIN_SECRET", "test-admin-secret-key")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("PUBLIC_BASE_URL", "http://localhost:8000")

import pytest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models import PaymentLink, Payment


class TestPaymentLinkCreation:
    """Test creating payment links."""

    def test_create_payment_link(self, client, test_merchant):
        merchant, raw_key = test_merchant
        resp = client.post(
            "/payment-links",
            json={"amount": 1500, "description": "Photography deposit"},
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["amount"] == 1500
        assert data["currency"] == "KES"
        assert data["status"] == "ACTIVE"
        assert data["description"] == "Photography deposit"
        assert data["public_id"]
        assert data["payment_url"].endswith(f"/pay/{data['public_id']}")

    def test_amount_must_be_greater_than_zero(self, client, test_merchant):
        merchant, raw_key = test_merchant
        resp = client.post(
            "/payment-links",
            json={"amount": 0},
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 422

        resp = client.post(
            "/payment-links",
            json={"amount": -100},
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 422

    def test_public_id_is_generated(self, client, test_merchant):
        merchant, raw_key = test_merchant
        resp = client.post(
            "/payment-links",
            json={"amount": 500},
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["public_id"]
        assert len(data["public_id"]) > 10

    def test_public_id_is_unique(self, client, test_merchant, db):
        merchant, raw_key = test_merchant
        public_ids = set()
        for i in range(5):
            resp = client.post(
                "/payment-links",
                json={"amount": 100 + i},
                headers={"X-API-Key": raw_key},
            )
            assert resp.status_code == 200
            public_ids.add(resp.json()["public_id"])
        assert len(public_ids) == 5

    def test_payment_url_is_generated(self, client, test_merchant):
        merchant, raw_key = test_merchant
        resp = client.post(
            "/payment-links",
            json={"amount": 1000},
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "http://localhost:8000/pay/" in data["payment_url"]

    def test_missing_account_reference_is_generated(self, client, test_merchant):
        merchant, raw_key = test_merchant
        resp = client.post(
            "/payment-links",
            json={"amount": 1000},
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["account_reference"]
        assert data["account_reference"].startswith("PL-")

    def test_existing_account_reference_is_preserved(self, client, test_merchant):
        merchant, raw_key = test_merchant
        resp = client.post(
            "/payment-links",
            json={"amount": 1000, "account_reference": "WEDDING-001"},
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["account_reference"] == "WEDDING-001"

    def test_description_is_optional(self, client, test_merchant):
        merchant, raw_key = test_merchant
        resp = client.post(
            "/payment-links",
            json={"amount": 1000},
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] is None

    def test_requires_authentication(self, client):
        resp = client.post(
            "/payment-links",
            json={"amount": 1000},
        )
        assert resp.status_code == 401


class TestPaymentLinkListing:
    """Test listing payment links."""

    def test_list_own_links(self, client, test_merchant):
        merchant, raw_key = test_merchant
        # Create 3 links
        for i in range(3):
            client.post(
                "/payment-links",
                json={"amount": 100 + i},
                headers={"X-API-Key": raw_key},
            )

        resp = client.get(
            "/payment-links",
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["links"]) == 3

    def test_cannot_see_other_merchant_links(self, client, test_merchant, db):
        from app.models import Merchant
        from app.security import generate_api_key

        merchant, raw_key = test_merchant
        # Create another merchant
        merchant2 = Merchant(
            business_name="Other Business",
            email="other@example.com",
            phone="254799999999",
            status="active",
        )
        raw_key2, key_prefix2, key_hash2 = generate_api_key()
        merchant2.api_key_prefix = key_prefix2
        merchant2.api_key_hash = key_hash2
        db.add(merchant2)
        db.commit()

        # Create a link for merchant2
        client.post(
            "/payment-links",
            json={"amount": 999},
            headers={"X-API-Key": raw_key2},
        )

        # Merchant1 should not see merchant2's links
        resp = client.get(
            "/payment-links",
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert len(data["links"]) == 0


class TestPaymentLinkRetrieval:
    """Test getting a single payment link."""

    def test_get_own_link(self, client, test_merchant):
        merchant, raw_key = test_merchant
        create_resp = client.post(
            "/payment-links",
            json={"amount": 1500, "description": "Test"},
            headers={"X-API-Key": raw_key},
        )
        public_id = create_resp.json()["public_id"]

        resp = client.get(
            f"/payment-links/{public_id}",
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["public_id"] == public_id
        assert data["amount"] == 1500

    def test_cannot_retrieve_other_merchant_link(self, client, test_merchant, db):
        from app.models import Merchant
        from app.security import generate_api_key

        merchant, raw_key = test_merchant
        merchant2 = Merchant(
            business_name="Other Business",
            email="other@example.com",
            phone="254799999999",
            status="active",
        )
        raw_key2, key_prefix2, key_hash2 = generate_api_key()
        merchant2.api_key_prefix = key_prefix2
        merchant2.api_key_hash = key_hash2
        db.add(merchant2)
        db.commit()

        # Create link for merchant2
        create_resp = client.post(
            "/payment-links",
            json={"amount": 999},
            headers={"X-API-Key": raw_key2},
        )
        public_id = create_resp.json()["public_id"]

        # Merchant1 cannot access it
        resp = client.get(
            f"/payment-links/{public_id}",
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 404

    def test_nonexistent_link_returns_404(self, client, test_merchant):
        merchant, raw_key = test_merchant
        resp = client.get(
            "/payment-links/nonexistent_id",
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 404


class TestPaymentLinkDisable:
    """Test disabling payment links."""

    def test_disable_active_link(self, client, test_merchant):
        merchant, raw_key = test_merchant
        create_resp = client.post(
            "/payment-links",
            json={"amount": 1000},
            headers={"X-API-Key": raw_key},
        )
        public_id = create_resp.json()["public_id"]

        resp = client.post(
            f"/payment-links/{public_id}/disable",
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "DISABLED"

    def test_cannot_disable_already_disabled_link(self, client, test_merchant):
        merchant, raw_key = test_merchant
        create_resp = client.post(
            "/payment-links",
            json={"amount": 1000},
            headers={"X-API-Key": raw_key},
        )
        public_id = create_resp.json()["public_id"]

        # Disable once
        client.post(
            f"/payment-links/{public_id}/disable",
            headers={"X-API-Key": raw_key},
        )

        # Try again
        resp = client.post(
            f"/payment-links/{public_id}/disable",
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 400
        assert "DISABLED" in resp.json()["detail"]

    def test_expired_link_becomes_expired_on_access(self, client, test_merchant):
        merchant, raw_key = test_merchant
        # Create a link that expires in the past
        past_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        create_resp = client.post(
            "/payment-links",
            json={"amount": 1000, "expires_at": past_time.isoformat()},
            headers={"X-API-Key": raw_key},
        )
        public_id = create_resp.json()["public_id"]

        # Access the link - should be marked as expired
        resp = client.get(
            f"/payment-links/{public_id}",
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "EXPIRED"

    def test_paid_link_cannot_be_reactivated(self, client, test_merchant, db):
        merchant, raw_key = test_merchant
        create_resp = client.post(
            "/payment-links",
            json={"amount": 1000},
            headers={"X-API-Key": raw_key},
        )
        public_id = create_resp.json()["public_id"]

        # Manually set status to PAID in DB
        link = db.query(PaymentLink).filter(PaymentLink.public_id == public_id).first()
        link.status = "PAID"
        db.commit()

        # Try to disable - should fail because status is not ACTIVE
        resp = client.post(
            f"/payment-links/{public_id}/disable",
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 400
        assert "PAID" in resp.json()["detail"]

    def test_cannot_disable_other_merchant_link(self, client, test_merchant, db):
        from app.models import Merchant
        from app.security import generate_api_key

        merchant, raw_key = test_merchant
        merchant2 = Merchant(
            business_name="Other Business",
            email="other@example.com",
            phone="254799999999",
            status="active",
        )
        raw_key2, key_prefix2, key_hash2 = generate_api_key()
        merchant2.api_key_prefix = key_prefix2
        merchant2.api_key_hash = key_hash2
        db.add(merchant2)
        db.commit()

        # Create link for merchant2
        create_resp = client.post(
            "/payment-links",
            json={"amount": 999},
            headers={"X-API-Key": raw_key2},
        )
        public_id = create_resp.json()["public_id"]

        # Merchant1 cannot disable it
        resp = client.post(
            f"/payment-links/{public_id}/disable",
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 404


class TestPaymentLinkRelationship:
    """Test PaymentLink -> Payment relationship."""

    def test_payment_link_permits_multiple_payment_attempts(self, client, test_merchant, db):
        from app.models import Payment

        merchant, raw_key = test_merchant
        create_resp = client.post(
            "/payment-links",
            json={"amount": 1000},
            headers={"X-API-Key": raw_key},
        )
        public_id = create_resp.json()["public_id"]
        link = db.query(PaymentLink).filter(PaymentLink.public_id == public_id).first()

        # Create multiple payments linked to the same payment link
        for i in range(3):
            payment = Payment(
                merchant_id=merchant.id,
                phone=f"25470000000{i}",
                amount=1000,
                checkout_request_id=f"ws_CO_{i}",
                status="PENDING",
                payment_link_id=link.id,
            )
            db.add(payment)
        db.commit()

        payments = db.query(Payment).filter(Payment.payment_link_id == link.id).all()
        assert len(payments) == 3


class TestPublicEndpoint:
    """Test the public payment link lookup endpoint."""

    def test_public_lookup_returns_link(self, client, test_merchant):
        merchant, raw_key = test_merchant
        create_resp = client.post(
            "/payment-links",
            json={"amount": 1500, "description": "Public test"},
            headers={"X-API-Key": raw_key},
        )
        public_id = create_resp.json()["public_id"]

        resp = client.get(f"/pay/{public_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["public_id"] == public_id
        assert data["amount"] == 1500
        assert "merchant_id" not in data
        assert "id" not in data

    def test_public_lookup_no_auth_required(self, client, test_merchant):
        merchant, raw_key = test_merchant
        create_resp = client.post(
            "/payment-links",
            json={"amount": 1000},
            headers={"X-API-Key": raw_key},
        )
        public_id = create_resp.json()["public_id"]

        # No auth header at all
        resp = client.get(f"/pay/{public_id}")
        assert resp.status_code == 200

    def test_expired_link_returns_410(self, client, test_merchant):
        merchant, raw_key = test_merchant
        past_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        create_resp = client.post(
            "/payment-links",
            json={"amount": 1000, "expires_at": past_time.isoformat()},
            headers={"X-API-Key": raw_key},
        )
        public_id = create_resp.json()["public_id"]

        resp = client.get(f"/pay/{public_id}")
        assert resp.status_code == 410

    def test_disabled_link_returns_410(self, client, test_merchant):
        merchant, raw_key = test_merchant
        create_resp = client.post(
            "/payment-links",
            json={"amount": 1000},
            headers={"X-API-Key": raw_key},
        )
        public_id = create_resp.json()["public_id"]

        # Disable it
        client.post(
            f"/payment-links/{public_id}/disable",
            headers={"X-API-Key": raw_key},
        )

        resp = client.get(f"/pay/{public_id}")
        assert resp.status_code == 410

    def test_nonexistent_link_returns_404(self, client):
        resp = client.get("/pay/nonexistent_id")
        assert resp.status_code == 404
