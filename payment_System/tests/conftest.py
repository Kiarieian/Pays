import os
import sys

# Must be set before any app module imports
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", "XIkBuofwH6Jk55CTrQ6ZeJwGmCWjRclh5stFnS0QQuU=")
os.environ.setdefault("ADMIN_SECRET", "test-admin-secret-key")
os.environ.setdefault("ENVIRONMENT", "test")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add payment_system to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import Base, get_db
from app.models import Merchant, Payment, Disbursement
from app.security import generate_api_key
from app.main import app


TEST_DATABASE_URL = "sqlite:///./test.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Reset all rate limiter counters before each test."""
    from app.rate_limit import (
        payment_limiter, disbursement_limiter, auth_limiter,
        general_api_limiter, admin_limiter,
    )
    for limiter in (payment_limiter, disbursement_limiter, auth_limiter,
                    general_api_limiter, admin_limiter):
        limiter._counts.clear()
    yield
    for limiter in (payment_limiter, disbursement_limiter, auth_limiter,
                    general_api_limiter, admin_limiter):
        limiter._counts.clear()


@pytest.fixture(autouse=True)
def setup_database():
    """Create fresh tables for each test."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db():
    """Provide a test database session."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_merchant(db):
    """Create and return an active merchant with API key."""
    merchant = Merchant(
        business_name="Test Business",
        email="test@example.com",
        phone="254700000000",
        status="active",
    )
    raw_key, key_prefix, key_hash = generate_api_key()
    merchant.api_key_prefix = key_prefix
    merchant.api_key_hash = key_hash

    # Set dummy Daraja credentials
    merchant.set_daraja_credentials(
        consumer_key="test_consumer_key",
        consumer_secret="test_consumer_secret",
        passkey="test_passkey",
        shortcode="174379",
        callback_base_url="https://example.com",
        environment="sandbox",
    )

    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return merchant, raw_key


@pytest.fixture
def test_merchant_b2c(db):
    """Create and return an active merchant with B2C credentials."""
    merchant = Merchant(
        business_name="B2C Business",
        email="b2c@example.com",
        phone="254711111111",
        status="active",
    )
    raw_key, key_prefix, key_hash = generate_api_key()
    merchant.api_key_prefix = key_prefix
    merchant.api_key_hash = key_hash

    merchant.set_daraja_credentials(
        consumer_key="test_consumer_key",
        consumer_secret="test_consumer_secret",
        passkey="test_passkey",
        shortcode="174379",
        callback_base_url="https://example.com",
        environment="sandbox",
    )
    merchant.set_b2c_credentials(
        shortcode="174379",
        initiator_name="testinitiator",
        security_credential="test_security_credential",
    )

    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return merchant, raw_key


@pytest.fixture
def pending_merchant(db):
    """Create a pending (not yet activated) merchant."""
    merchant = Merchant(
        business_name="Pending Business",
        email="pending@example.com",
        phone="254722222222",
        status="pending",
    )
    raw_key, key_prefix, key_hash = generate_api_key()
    merchant.api_key_prefix = key_prefix
    merchant.api_key_hash = key_hash

    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return merchant, raw_key


def override_get_db(test_db_session):
    """Dependency override for FastAPI."""
    def _get_db():
        try:
            yield test_db_session
        finally:
            pass
    return _get_db


@pytest.fixture
def client(db):
    """Provide a FastAPI test client with database override."""
    from fastapi.testclient import TestClient

    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
