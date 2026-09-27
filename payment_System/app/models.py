from sqlalchemy import (
    Boolean, Column, Integer, String, DateTime, ForeignKey,
    LargeBinary, Index, UniqueConstraint, func,
)
from datetime import datetime, timezone

from app.database import Base
from app.security import encrypt_value, decrypt_value


class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(Integer, primary_key=True, index=True)

    business_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String, unique=True, nullable=False)

    # active | pending | suspended
    status = Column(String, default="pending", nullable=False, index=True)

    # Our gateway API key (merchant calls US with this — server-to-server only)
    api_key_prefix = Column(String, unique=True, nullable=True, index=True)
    api_key_hash = Column(String, nullable=True)

    # Dashboard login password (bcrypt hash). Set via /merchants/set-password.
    password_hash = Column(String, nullable=True)

    # Merchant's OWN Daraja credentials (BYO model)
    daraja_environment = Column(String, default="sandbox")
    daraja_shortcode = Column(String, nullable=True)
    daraja_consumer_key_enc = Column(LargeBinary, nullable=True)
    daraja_consumer_secret_enc = Column(LargeBinary, nullable=True)
    daraja_passkey_enc = Column(LargeBinary, nullable=True)
    daraja_callback_base_url = Column(String, nullable=True)

    # B2C / disbursement credentials (optional)
    b2c_shortcode = Column(String, nullable=True)
    b2c_initiator_name = Column(String, nullable=True)
    b2c_security_credential_enc = Column(LargeBinary, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __init__(self, business_name, email, phone, status="pending"):
        self.business_name = business_name
        self.email = email
        self.phone = phone
        self.status = status

    def set_daraja_credentials(self, consumer_key, consumer_secret, passkey,
                                shortcode, callback_base_url, environment="sandbox"):
        self.daraja_consumer_key_enc = encrypt_value(consumer_key)
        self.daraja_consumer_secret_enc = encrypt_value(consumer_secret)
        self.daraja_passkey_enc = encrypt_value(passkey)
        self.daraja_shortcode = shortcode
        self.daraja_callback_base_url = callback_base_url
        self.daraja_environment = environment

    def get_daraja_credentials(self):
        return {
            "consumer_key": decrypt_value(self.daraja_consumer_key_enc),
            "consumer_secret": decrypt_value(self.daraja_consumer_secret_enc),
            "passkey": decrypt_value(self.daraja_passkey_enc),
            "shortcode": self.daraja_shortcode,
            "callback_base_url": self.daraja_callback_base_url,
            "environment": self.daraja_environment,
        }

    def set_b2c_credentials(self, shortcode, initiator_name, security_credential):
        self.b2c_shortcode = shortcode
        self.b2c_initiator_name = initiator_name
        self.b2c_security_credential_enc = encrypt_value(security_credential)

    def get_b2c_credentials(self):
        return {
            "shortcode": self.b2c_shortcode,
            "initiator_name": self.b2c_initiator_name,
            "security_credential": decrypt_value(self.b2c_security_credential_enc),
        }

    def has_b2c_credentials(self) -> bool:
        return bool(self.b2c_shortcode and self.b2c_initiator_name
                     and self.b2c_security_credential_enc)


class MerchantSession(Base):
    """Browser session tokens for dashboard access."""
    __tablename__ = "merchant_sessions"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False, index=True)

    # Opaque token (secrets.token_urlsafe(32)), stored as SHA-256 hash
    token_hash = Column(String, unique=True, nullable=False, index=True)

    # Metadata
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    last_used_at = Column(DateTime, nullable=True)

    # Optional: user-agent for revocation UI
    user_agent = Column(String, nullable=True)


class Payment(Base):
    """Inbound customer payments (STK push / C2B)."""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False, index=True)

    phone = Column(String, nullable=False)
    # Integer for KSh amounts (no fractional currency)
    amount = Column(Integer, nullable=False)
    payment_method = Column(String, nullable=False, default="stk_push")

    # Payment lifecycle: PENDING | SUCCESS | FAILED | TIMEOUT | CANCELLED
    status = Column(String, default="PENDING", nullable=False, index=True)

    checkout_request_id = Column(String, unique=True, nullable=True, index=True)
    mpesa_receipt = Column(String, nullable=True, index=True)

    # Idempotency: prevents duplicate payment creation from merchant retries
    idempotency_key = Column(String, nullable=True, index=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_payments_merchant_status", "merchant_id", "status"),
        Index("ix_payments_merchant_created", "merchant_id", "created_at"),
        # Partial unique: only enforce when idempotency_key is NOT NULL.
        # SQL UNIQUE treats multiple NULLs as distinct, so this is safe.
        Index(
            "uq_payments_merchant_idempotency",
            "merchant_id",
            "idempotency_key",
            unique=True,
            postgresql_where="idempotency_key IS NOT NULL",
        ),
    )


class Disbursement(Base):
    """Outgoing B2C payments from merchant to customer."""
    __tablename__ = "disbursements"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False, index=True)

    phone = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    remarks = Column(String, nullable=True)

    # PENDING | SUCCESS | FAILED | TIMEOUT
    status = Column(String, default="PENDING", nullable=False, index=True)

    conversation_id = Column(String, unique=True, nullable=True, index=True)
    originator_conversation_id = Column(String, nullable=True)
    mpesa_receipt = Column(String, nullable=True, index=True)
    result_desc = Column(String, nullable=True)

    idempotency_key = Column(String, nullable=True, index=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_disbursements_merchant_status", "merchant_id", "status"),
        Index(
            "uq_disbursements_merchant_idempotency",
            "merchant_id",
            "idempotency_key",
            unique=True,
            postgresql_where="idempotency_key IS NOT NULL",
        ),
    )


class PaymentLink(Base):
    """Merchant payment links (defined but not yet routed)."""
    __tablename__ = "payment_links"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False, index=True)

    title = Column(String, nullable=False)
    description = Column(String)
    amount = Column(Integer, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    active = Column(Boolean, default=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class APIRequestLog(Base):
    """Every call a merchant makes to our gateway."""
    __tablename__ = "api_request_logs"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=True, index=True)

    endpoint = Column(String, nullable=False)
    status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Integer, nullable=True)
    request_id = Column(String, nullable=True, index=True)
    error_message = Column(String, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    __table_args__ = (
        Index("ix_api_logs_merchant_created", "merchant_id", "created_at"),
    )
