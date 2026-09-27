"""Session (browser) authentication tests."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta

from app.models import MerchantSession
from app.security import hash_password, generate_session_token, hash_session_token


class TestLogin:
    def test_login_success(self, client, db, test_merchant):
        merchant, _ = test_merchant
        # Set a password
        merchant.password_hash = hash_password("securepass123")
        db.commit()

        response = client.post("/auth/login", json={
            "email": merchant.email,
            "password": "securepass123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "session_token" in data
        assert data["merchant_id"] == merchant.id
        assert data["business_name"] == merchant.business_name

    def test_login_wrong_password(self, client, db, test_merchant):
        merchant, _ = test_merchant
        merchant.password_hash = hash_password("correctpass")
        db.commit()

        response = client.post("/auth/login", json={
            "email": merchant.email,
            "password": "wrongpass",
        })
        assert response.status_code == 401

    def test_login_nonexistent_email(self, client):
        response = client.post("/auth/login", json={
            "email": "nobody@example.com",
            "password": "anything",
        })
        assert response.status_code == 401

    def test_login_no_password_set(self, client, db, test_merchant):
        merchant, _ = test_merchant
        # Don't set a password
        response = client.post("/auth/login", json={
            "email": merchant.email,
            "password": "anything",
        })
        assert response.status_code == 400
        assert "Password not set" in response.json()["detail"]

    def test_login_pending_merchant_forbidden(self, client, db, pending_merchant):
        merchant, _ = pending_merchant
        merchant.password_hash = hash_password("pass12345")
        db.commit()

        response = client.post("/auth/login", json={
            "email": merchant.email,
            "password": "pass12345",
        })
        assert response.status_code == 403


class TestSessionAuth:
    def _login(self, client, email, password):
        """Helper to login and return session token."""
        r = client.post("/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200
        return r.json()["session_token"]

    def test_session_profile(self, client, db, test_merchant):
        merchant, _ = test_merchant
        merchant.password_hash = hash_password("mypass123")
        db.commit()

        token = self._login(client, merchant.email, "mypass123")
        response = client.get("/merchants/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["business_name"] == "Test Business"

    def test_session_payments(self, client, db, test_merchant):
        from app.models import Payment

        merchant, _ = test_merchant
        merchant.password_hash = hash_password("mypass123")
        db.commit()

        p = Payment(phone="254712345678", amount=100, merchant_id=merchant.id, checkout_request_id="ws_CO_SESS")
        db.add(p)
        db.commit()

        token = self._login(client, merchant.email, "mypass123")
        response = client.get("/payments", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_session_expired_rejected(self, client, db, test_merchant):
        merchant, _ = test_merchant
        merchant.password_hash = hash_password("mypass123")
        db.commit()

        # Create an expired session directly
        raw_token, token_hash = generate_session_token()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        session = MerchantSession(
            merchant_id=merchant.id,
            token_hash=token_hash,
            expires_at=now - timedelta(hours=1),  # Already expired
        )
        db.add(session)
        db.commit()

        response = client.get("/merchants/me", headers={"Authorization": f"Bearer {raw_token}"})
        assert response.status_code == 401

    def test_invalid_token_rejected(self, client):
        response = client.get("/merchants/me", headers={"Authorization": "Bearer invalidtoken123"})
        assert response.status_code == 401

    def test_no_auth_header_rejected(self, client):
        response = client.get("/merchants/me")
        assert response.status_code == 401

    def test_session_scoped_to_merchant(self, client, db, test_merchant):
        from app.models import Payment

        merchant_a, _ = test_merchant
        merchant_a.password_hash = hash_password("pass_aaa")
        db.commit()

        # Create merchant B with its own session
        from app.models import Merchant
        from app.security import generate_api_key
        merchant_b = Merchant(
            business_name="Business B",
            email="sess_b@example.com",
            phone="254777777777",
            status="active",
        )
        raw_key_b, prefix_b, hash_b = generate_api_key()
        merchant_b.api_key_prefix = prefix_b
        merchant_b.api_key_hash = hash_b
        merchant_b.password_hash = hash_password("pass_bbb")
        db.add(merchant_b)
        db.commit()
        db.refresh(merchant_b)

        # Add payment for merchant B
        p = Payment(phone="254700000001", amount=999, merchant_id=merchant_b.id, checkout_request_id="ws_CO_SESS_B")
        db.add(p)
        db.commit()

        # Login as merchant A — should NOT see merchant B's payment
        token_a = self._login(client, merchant_a.email, "pass_aaa")
        response = client.get("/payments", headers={"Authorization": f"Bearer {token_a}"})
        assert response.status_code == 200
        for item in response.json():
            assert item["checkout_request_id"] != "ws_CO_SESS_B"


class TestLogout:
    def test_logout_invalidates_session(self, client, db, test_merchant):
        merchant, _ = test_merchant
        merchant.password_hash = hash_password("mypass123")
        db.commit()

        r = client.post("/auth/login", json={"email": merchant.email, "password": "mypass123"})
        token = r.json()["session_token"]

        # Verify session works
        r = client.get("/merchants/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200

        # Logout
        r = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200

        # Session should now be invalid
        r = client.get("/merchants/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


class TestSetPassword:
    def test_set_password(self, client, db, test_merchant):
        merchant, _ = test_merchant
        merchant.password_hash = hash_password("oldpass123")
        db.commit()

        # Login with old password
        token_r = client.post("/auth/login", json={"email": merchant.email, "password": "oldpass123"})
        token = token_r.json()["session_token"]

        # Set new password
        r = client.post("/merchants/set-password",
            json={"password": "newpass456"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200

        # Old password should no longer work
        r = client.post("/auth/login", json={"email": merchant.email, "password": "oldpass123"})
        assert r.status_code == 401

        # New password should work
        r = client.post("/auth/login", json={"email": merchant.email, "password": "newpass456"})
        assert r.status_code == 200

    def test_set_password_too_short(self, client, db, test_merchant):
        merchant, _ = test_merchant
        merchant.password_hash = hash_password("oldpass123")
        db.commit()

        token_r = client.post("/auth/login", json={"email": merchant.email, "password": "oldpass123"})
        token = token_r.json()["session_token"]

        r = client.post("/merchants/set-password",
            json={"password": "short"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 422  # Validation error (min 8 chars)


class TestInitialPasswordSetup:
    """Test initial password provisioning via API key (onboarding flow)."""

    def test_api_key_sets_initial_password(self, client, test_merchant):
        """Active merchant + valid API key + no password → set password → 200."""
        _, raw_key = test_merchant

        r = client.post("/merchants/set-password",
            json={"password": "initial123"},
            headers={"X-API-Key": raw_key},
        )
        assert r.status_code == 200
        assert "Password set" in r.json()["message"]

    def test_invalid_api_key_rejected(self, client):
        """Invalid API key → 401."""
        r = client.post("/merchants/set-password",
            json={"password": "initial123"},
            headers={"X-API-Key": "sk_live_invalidkey123"},
        )
        assert r.status_code == 401

    def test_no_auth_rejected(self, client):
        """No API key, no session → 401."""
        r = client.post("/merchants/set-password",
            json={"password": "initial123"},
        )
        assert r.status_code == 401

    def test_pending_merchant_rejected(self, client, pending_merchant):
        """Valid API key + pending merchant → 403."""
        _, raw_key = pending_merchant

        r = client.post("/merchants/set-password",
            json={"password": "initial123"},
            headers={"X-API-Key": raw_key},
        )
        assert r.status_code == 403

    def test_merchant_a_cannot_set_merchant_b_password(self, client, db, test_merchant):
        """Merchant A's API key must not set Merchant B's password."""
        from app.models import Merchant
        from app.security import generate_api_key

        merchant_a, key_a = test_merchant

        # Create merchant B
        merchant_b = Merchant(
            business_name="Business B",
            email="setpw_b@example.com",
            phone="254788888888",
            status="active",
        )
        raw_key_b, prefix_b, hash_b = generate_api_key()
        merchant_b.api_key_prefix = prefix_b
        merchant_b.api_key_hash = hash_b
        db.add(merchant_b)
        db.commit()
        db.refresh(merchant_b)

        # Merchant A tries to set merchant B's password — should fail
        # (A's key authenticates as A, so it sets A's password, not B's)
        r = client.post("/merchants/set-password",
            json={"password": "attacker123"},
            headers={"X-API-Key": key_a},
        )
        assert r.status_code == 200  # Sets A's password

        # Merchant B should still have no password
        db.refresh(merchant_b)
        assert merchant_b.password_hash is None

    def test_password_enables_login(self, client, test_merchant):
        """Full onboarding: set password via API key → login with email+password."""
        merchant, raw_key = test_merchant

        # Step 1: Set initial password via API key
        r = client.post("/merchants/set-password",
            json={"password": "onboard123"},
            headers={"X-API-Key": raw_key},
        )
        assert r.status_code == 200

        # Step 2: Login with email + password
        r = client.post("/auth/login", json={
            "email": merchant.email,
            "password": "onboard123",
        })
        assert r.status_code == 200
        token = r.json()["session_token"]
        assert "session_token" in r.json()

        # Step 3: Use session to access profile
        r = client.get("/merchants/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["business_name"] == "Test Business"

    def test_session_password_change_still_works(self, client, db, test_merchant):
        """Existing session-based password change is preserved."""
        merchant, _ = test_merchant
        merchant.password_hash = hash_password("oldpass123")
        db.commit()

        # Login with old password
        token_r = client.post("/auth/login", json={"email": merchant.email, "password": "oldpass123"})
        token = token_r.json()["session_token"]

        # Change password via session
        r = client.post("/merchants/set-password",
            json={"password": "newpass456"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200

        # New password works
        r = client.post("/auth/login", json={"email": merchant.email, "password": "newpass456"})
        assert r.status_code == 200

    def test_api_key_not_returned_in_response(self, client, test_merchant):
        """set-password response must not contain the API key."""
        _, raw_key = test_merchant

        r = client.post("/merchants/set-password",
            json={"password": "initial123"},
            headers={"X-API-Key": raw_key},
        )
        assert r.status_code == 200
        response_text = r.text
        assert "sk_live_" not in response_text


class TestDualAuth:
    """Test that both session tokens and API keys work for the same endpoints."""

    @patch("app.main.stk_push")
    def test_pay_with_api_key(self, mock_stk, client, test_merchant):
        _, raw_key = test_merchant
        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_DUAL_KEY"}

        r = client.post("/pay", json={
            "phone": "254712345678",
            "amount": 100,
        }, headers={"X-API-Key": raw_key})
        assert r.status_code == 200

    @patch("app.main.stk_push")
    def test_pay_with_session_token(self, mock_stk, client, db, test_merchant):
        merchant, _ = test_merchant
        merchant.password_hash = hash_password("mypass123")
        db.commit()

        mock_stk.return_value = {"CheckoutRequestID": "ws_CO_DUAL_SESS"}

        token_r = client.post("/auth/login", json={"email": merchant.email, "password": "mypass123"})
        token = token_r.json()["session_token"]

        r = client.post("/pay", json={
            "phone": "254712345678",
            "amount": 100,
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
