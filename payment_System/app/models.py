from sqlalchemy import Boolean, Column, Engine, Integer, String, DateTime, ForeignKey, LargeBinary, Numeric, create_engine
from datetime import datetime
import uuid

from app.database import Base, engine
from app.security import encrypt_value, decrypt_value


Base.metadata.create_all(bind=engine)

class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(Integer, primary_key=True, index=True)

    business_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String, unique=True, nullable=False)

    # active | pending | suspended
    status = Column(String, default="pending", nullable=False)

    # ---- Our gateway API key (merchant calls US with this) ----
    api_key_prefix = Column(String, unique=True, nullable=True, index=True)
    api_key_hash = Column(String, nullable=True)

    # ---- Merchant's OWN Daraja credentials (BYO model) ----
    # in-memory, right before calling Safaricom on the merchant's behalf.
    daraja_environment = Column(String, default="sandbox")  # sandbox | production
    daraja_shortcode = Column(String, nullable=True)
    daraja_consumer_key_enc = Column(LargeBinary, nullable=True)
    daraja_consumer_secret_enc = Column(LargeBinary, nullable=True)
    daraja_passkey_enc = Column(LargeBinary, nullable=True)
    daraja_callback_base_url = Column(String, nullable=True)

    # ---- B2C / disbursement credentials (optional, separate from C2B) ----

    b2c_shortcode = Column(String, nullable=True)
    b2c_initiator_name = Column(String, nullable=True)
    b2c_security_credential_enc = Column(LargeBinary, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    

    def __init__(self, business_name, email, phone, status="active"):
        self.business_name = business_name
        self.email = email
        self.phone = phone
        self.status = status

    # ---- Convenience helpers to set/get encrypted fields ----
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


class Payment(Base):
    """Inbound customer payments (STK push / C2B)."""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False)

    phone = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    payment_method = Column(String, nullable=False, default="stk_push")
    status = Column(String, default="Pending")

    checkout_request_id = Column(String, unique=True, nullable=True)
    mpesa_receipt = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    def __init__(self, phone, amount, checkout_request_id, status="Pending",
                 mpesa_receipt=None, merchant_id=None, payment_method="stk_push"):
        self.phone = phone
        self.amount = amount
        self.checkout_request_id = checkout_request_id
        self.status = status
        self.mpesa_receipt = mpesa_receipt
        self.merchant_id = merchant_id
        self.payment_method = payment_method


class Disbursement(Base):
    """Outbound B2C payments — always sent using the MERCHANT's own
    B2C credentials, never ours. We never hold or move these funds."""
    __tablename__ = "disbursements"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False)

    phone = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    remarks = Column(String, nullable=True)
    status = Column(String, default="Pending")  # Pending | Success | Failed

    conversation_id = Column(String, unique=True, nullable=True)
    originator_conversation_id = Column(String, nullable=True)
    mpesa_receipt = Column(String, nullable=True)
    result_desc = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class PaymentLink(Base):
    __tablename__ = "payment_links"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False)

    title = Column(String, nullable=False)
    description = Column(String)
    amount = Column(Integer, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class APIRequestLog(Base):
    """Every call a merchant makes to OUR gateway — powers the
    'API tracking' dashboard (volume, success rate, latency, errors)."""
    __tablename__ = "api_request_logs"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=True)

    endpoint = Column(String, nullable=False)       # e.g. "stk_push", "generate_qr", "disburse"
    status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Integer, nullable=True)
    request_id = Column(String, default=lambda: str(uuid.uuid4()))
    error_message = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)