import logging
import secrets
import time
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Header, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field

from app.config import get_settings
from app.database import get_db
from app.models import Base, Merchant, MerchantSession, Payment, PaymentLink, APIRequestLog
from app.services.payment_service import create_payment, create_disbursement, log_api_request
from app.services.payment_link_service import (
    create_payment_link, disable_payment_link, check_and_expire_link,
)
from app.security import (
    generate_api_key, verify_api_key,
    hash_password, verify_password,
    generate_session_token, hash_session_token,
)
from app.daraja import stk_push, generate_qr, b2c_disbursement, normalize_phone
from app.callbacks import router as callback_router
from app.rate_limit import RateLimitMiddleware

SESSION_EXPIRY_HOURS = 24

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.app.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("daraja.main")

app = FastAPI(title=settings.app.api_title, version=settings.app.api_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)

app.include_router(callback_router, prefix="/api/payment")


# ---------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------
class MerchantSignupRequest(BaseModel):
    business_name: str
    email: EmailStr
    phone: str


class DarajaCredentialsRequest(BaseModel):
    consumer_key: str
    consumer_secret: str
    passkey: str
    shortcode: str
    callback_base_url: str
    environment: str = "sandbox"


class B2CCredentialsRequest(BaseModel):
    shortcode: str
    initiator_name: str
    security_credential: str


class PaymentRequest(BaseModel):
    phone: str
    amount: int = Field(gt=0)
    account_reference: str | None = None
    idempotency_key: str | None = None


class QRRequest(BaseModel):
    amount: int = Field(gt=0)
    account_reference: str | None = None
    trx_code: str = "BG"


class DisbursementRequest(BaseModel):
    phone: str
    amount: int = Field(gt=0)
    remarks: str = "Disbursement"
    idempotency_key: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SetPasswordRequest(BaseModel):
    password: str = Field(min_length=8)


class LoginResponse(BaseModel):
    session_token: str
    merchant_id: int
    business_name: str


# ---------------------------------------------------------------------
# Session auth — browser/dashboard access
# ---------------------------------------------------------------------
def _expire_old_sessions(db: Session, merchant_id: int):
    """Delete expired sessions for a merchant."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.query(MerchantSession).filter(
        MerchantSession.merchant_id == merchant_id,
        MerchantSession.expires_at < now,
    ).delete()


def verify_session(
    request: Request,
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> Merchant:
    """Verify a Bearer session token and return the merchant."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token_h = hash_session_token(token)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    session = db.query(MerchantSession).filter(
        MerchantSession.token_hash == token_h,
        MerchantSession.expires_at > now,
    ).first()

    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    merchant = db.query(Merchant).filter(Merchant.id == session.merchant_id).first()
    if not merchant or merchant.status != "active":
        raise HTTPException(status_code=403, detail="Account is not active")

    # Update last_used_at (best-effort, don't fail request)
    session.last_used_at = now
    try:
        db.commit()
    except Exception:
        db.rollback()

    request.state.merchant = merchant
    request.state.auth_method = "session"
    return merchant


def get_current_merchant_or_session(
    request: Request,
    x_api_key: str = Header(None),
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> Merchant:
    """Accept either a session token (Bearer) or an API key (X-API-Key).
    Session auth is tried first. Falls back to API key for S2S calls."""
    # Try session token first
    if authorization and authorization.startswith("Bearer "):
        return verify_session(request, authorization, db)

    # Fall back to API key
    if x_api_key:
        if len(x_api_key) < 12:
            raise HTTPException(status_code=401, detail="Invalid API key")

        prefix = x_api_key[:12]
        merchant = db.query(Merchant).filter(Merchant.api_key_prefix == prefix).first()

        if not merchant or not merchant.api_key_hash or not verify_api_key(x_api_key, merchant.api_key_hash):
            raise HTTPException(status_code=401, detail="Invalid API key")

        if merchant.status != "active":
            raise HTTPException(status_code=403, detail=f"Merchant account is {merchant.status}")

        request.state.merchant = merchant
        request.state.auth_method = "api_key"
        return merchant

    raise HTTPException(status_code=401, detail="Not authenticated")


def _log(db: Session, merchant_id, endpoint, status_code, start_time, error=None):
    elapsed_ms = int((time.time() - start_time) * 1000)
    try:
        log_api_request(db, merchant_id, endpoint, status_code, elapsed_ms, error)
    except Exception:
        logger.exception("Failed to write API request log")


# ---------------------------------------------------------------------
# Admin auth
# ---------------------------------------------------------------------
def verify_admin(x_admin_key: str = Header(...)):
    if not secrets.compare_digest(x_admin_key, settings.security.admin_secret):
        raise HTTPException(status_code=403, detail="Invalid admin key")


# ---------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "version": settings.app.api_version}


@app.get("/")
def home():
    return {"message": "Daraja Payment Gateway Running"}


# ---------------------------------------------------------------------
# Merchant onboarding
# ---------------------------------------------------------------------
@app.post("/merchants/signup")
def merchant_signup(request: MerchantSignupRequest, db: Session = Depends(get_db)):
    existing = db.query(Merchant).filter(Merchant.email == request.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    merchant = Merchant(
        business_name=request.business_name,
        email=request.email,
        phone=request.phone,
        status="pending",
    )
    raw_key, key_prefix, key_hash = generate_api_key()
    merchant.api_key_prefix = key_prefix
    merchant.api_key_hash = key_hash

    db.add(merchant)
    db.commit()
    db.refresh(merchant)

    return {
        "merchant_id": merchant.id,
        "status": merchant.status,
        "api_key": raw_key,
        "message": "Save this API key now — it will not be shown again. "
                   "Your account is pending activation.",
    }


@app.post("/auth/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    merchant = db.query(Merchant).filter(Merchant.email == request.email).first()
    if not merchant:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not merchant.password_hash:
        raise HTTPException(
            status_code=400,
            detail="Password not set. Use POST /merchants/set-password first.",
        )

    if not verify_password(request.password, merchant.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if merchant.status != "active":
        raise HTTPException(status_code=403, detail=f"Account is {merchant.status}")

    # Clean up expired sessions
    _expire_old_sessions(db, merchant.id)

    # Create new session
    raw_token, token_hash = generate_session_token()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    session = MerchantSession(
        merchant_id=merchant.id,
        token_hash=token_hash,
        expires_at=now + timedelta(hours=SESSION_EXPIRY_HOURS),
    )
    db.add(session)
    db.commit()

    return LoginResponse(
        session_token=raw_token,
        merchant_id=merchant.id,
        business_name=merchant.business_name,
    )


@app.post("/auth/logout")
def logout(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(verify_session),
):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        token_h = hash_session_token(token)
        db.query(MerchantSession).filter(MerchantSession.token_hash == token_h).delete()
        db.commit()
    return {"message": "Logged out"}


@app.post("/merchants/set-password")
def set_password(
    request: SetPasswordRequest,
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant_or_session),
):
    merchant.password_hash = hash_password(request.password)
    db.commit()
    return {"message": "Password set. You can now log in via /auth/login."}


@app.post("/merchants/daraja-credentials")
def submit_daraja_credentials(
    request: DarajaCredentialsRequest,
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant_or_session),
):
    merchant.set_daraja_credentials(
        consumer_key=request.consumer_key,
        consumer_secret=request.consumer_secret,
        passkey=request.passkey,
        shortcode=request.shortcode,
        callback_base_url=request.callback_base_url,
        environment=request.environment,
    )
    db.commit()
    return {"message": "Daraja credentials saved"}


@app.post("/merchants/b2c-credentials")
def submit_b2c_credentials(
    request: B2CCredentialsRequest,
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant_or_session),
):
    merchant.set_b2c_credentials(
        shortcode=request.shortcode,
        initiator_name=request.initiator_name,
        security_credential=request.security_credential,
    )
    db.commit()
    return {"message": "B2C credentials saved"}


@app.get("/merchants/me")
def get_merchant_profile(merchant: Merchant = Depends(get_current_merchant_or_session)):
    return {
        "id": merchant.id,
        "business_name": merchant.business_name,
        "email": merchant.email,
        "status": merchant.status,
        "daraja_configured": bool(merchant.daraja_shortcode),
        "b2c_configured": merchant.has_b2c_credentials(),
    }


class AdminActivationRequest(BaseModel):
    merchant_id: int


class PaymentLinkCreateRequest(BaseModel):
    amount: int = Field(gt=0)
    description: str | None = None
    account_reference: str | None = None
    expires_at: datetime | None = None


class PaymentLinkResponse(BaseModel):
    id: int
    public_id: str
    amount: int
    currency: str
    description: str | None
    account_reference: str
    status: str
    expires_at: datetime | None
    payment_url: str
    created_at: datetime
    updated_at: datetime


@app.post("/admin/merchants/activate")
def activate_merchant(
    request: AdminActivationRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    merchant = db.query(Merchant).filter(Merchant.id == request.merchant_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    if merchant.status == "active":
        return {"merchant_id": merchant.id, "status": merchant.status}
    merchant.status = "active"
    db.commit()
    return {"merchant_id": merchant.id, "status": merchant.status}


# ---------------------------------------------------------------------
# STK Push
# ---------------------------------------------------------------------
@app.post("/pay")
def pay(
    request: PaymentRequest,
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant_or_session),
):
    start = time.time()
    try:
        phone = normalize_phone(request.phone)
    except ValueError as e:
        _log(db, merchant.id, "stk_push", 400, start, str(e))
        raise HTTPException(status_code=400, detail=str(e))

    if not merchant.daraja_shortcode:
        _log(db, merchant.id, "stk_push", 400, start, "No Daraja credentials configured")
        raise HTTPException(status_code=400, detail="Daraja credentials not configured for this merchant")

    try:
        response = stk_push(merchant, phone, request.amount, request.account_reference)
    except Exception as e:
        _log(db, merchant.id, "stk_push", 502, start, str(e))
        raise HTTPException(status_code=502, detail=f"Daraja request failed: {e}")

    checkout_id = response.get("CheckoutRequestID")
    payment = create_payment(
        db, phone, request.amount, checkout_id,
        merchant_id=merchant.id, payment_method="stk_push",
        idempotency_key=request.idempotency_key,
    )
    _log(db, merchant.id, "stk_push", 200, start)

    return {
        "payment_id": payment.id,
        "checkout_id": checkout_id,
        "status": payment.status,
    }


# ---------------------------------------------------------------------
# QR Code generation
# ---------------------------------------------------------------------
@app.post("/generate_qr")
def generate_qr_code(
    request: QRRequest,
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant_or_session),
):
    start = time.time()
    if not merchant.daraja_shortcode:
        _log(db, merchant.id, "generate_qr", 400, start, "No Daraja credentials configured")
        raise HTTPException(status_code=400, detail="Daraja credentials not configured for this merchant")

    account_ref = request.account_reference or str(uuid.uuid4())[:12]

    try:
        response = generate_qr(merchant, request.amount, account_ref, request.trx_code)
    except Exception as e:
        _log(db, merchant.id, "generate_qr", 502, start, str(e))
        raise HTTPException(status_code=502, detail=f"Daraja request failed: {e}")

    _log(db, merchant.id, "generate_qr", 200, start)

    return {
        "account_reference": account_ref,
        "qr_code_base64": response.get("QRCode"),
        "raw_response": response,
    }


# ---------------------------------------------------------------------
# B2C Disbursement
# ---------------------------------------------------------------------
@app.post("/disburse")
def disburse(
    request: DisbursementRequest,
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant_or_session),
):
    start = time.time()
    try:
        phone = normalize_phone(request.phone)
    except ValueError as e:
        _log(db, merchant.id, "disburse", 400, start, str(e))
        raise HTTPException(status_code=400, detail=str(e))

    if not merchant.has_b2c_credentials():
        _log(db, merchant.id, "disburse", 400, start, "No B2C credentials configured")
        raise HTTPException(
            status_code=400,
            detail="B2C credentials not configured. Merchant must have a "
                   "Safaricom-approved B2C shortcode first.",
        )

    try:
        response = b2c_disbursement(merchant, phone, request.amount, request.remarks)
    except Exception as e:
        _log(db, merchant.id, "disburse", 502, start, str(e))
        raise HTTPException(status_code=502, detail=f"Daraja request failed: {e}")

    conversation_id = response.get("ConversationID")
    originator_conversation_id = response.get("OriginatorConversationID")

    disbursement = create_disbursement(
        db, merchant.id, phone, request.amount, request.remarks,
        conversation_id, originator_conversation_id,
        idempotency_key=request.idempotency_key,
    )
    _log(db, merchant.id, "disburse", 200, start)

    return {
        "disbursement_id": disbursement.id,
        "conversation_id": conversation_id,
        "status": disbursement.status,
    }


# ---------------------------------------------------------------------
# Dashboard-style endpoints
# ---------------------------------------------------------------------
@app.get("/payments")
def get_payments(
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant_or_session),
):
    payments = db.query(Payment).filter(Payment.merchant_id == merchant.id).all()
    return [
        {
            "id": p.id,
            "phone": p.phone,
            "amount": p.amount,
            "status": p.status,
            "checkout_request_id": p.checkout_request_id,
            "mpesa_receipt": p.mpesa_receipt,
            "created_at": p.created_at,
        }
        for p in payments
    ]


@app.get("/usage")
def get_usage(
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant_or_session),
):
    logs = (
        db.query(APIRequestLog)
        .filter(APIRequestLog.merchant_id == merchant.id)
        .order_by(APIRequestLog.created_at.desc())
        .limit(100)
        .all()
    )
    total = len(logs)
    successes = len([l for l in logs if l.status_code < 400])
    return {
        "recent_requests": total,
        "success_rate": round(successes / total, 3) if total else None,
        "requests": [
            {
                "endpoint": l.endpoint,
                "status_code": l.status_code,
                "response_time_ms": l.response_time_ms,
                "created_at": l.created_at,
                "error_message": l.error_message,
            }
            for l in logs
        ],
    }


# ---------------------------------------------------------------------
# Payment Links
# ---------------------------------------------------------------------
@app.post("/payment-links", response_model=PaymentLinkResponse)
def create_link(
    request: PaymentLinkCreateRequest,
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant_or_session),
):
    start = time.time()
    link = create_payment_link(
        db,
        merchant_id=merchant.id,
        amount=request.amount,
        description=request.description,
        account_reference=request.account_reference,
        expires_at=request.expires_at,
    )
    _log(db, merchant.id, "create_payment_link", 200, start)
    payment_url = f"{settings.app.public_base_url}/pay/{link.public_id}"
    return PaymentLinkResponse(
        id=link.id,
        public_id=link.public_id,
        amount=link.amount,
        currency=link.currency,
        description=link.description,
        account_reference=link.account_reference,
        status=link.status,
        expires_at=link.expires_at,
        payment_url=payment_url,
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


@app.get("/payment-links")
def list_links(
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant_or_session),
    offset: int = 0,
    limit: int = 50,
):
    start = time.time()
    query = (
        db.query(PaymentLink)
        .filter(PaymentLink.merchant_id == merchant.id)
        .order_by(PaymentLink.created_at.desc())
    )
    total = query.count()
    links = query.offset(offset).limit(limit).all()
    _log(db, merchant.id, "list_payment_links", 200, start)
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "links": [
            {
                "id": l.id,
                "public_id": l.public_id,
                "amount": l.amount,
                "currency": l.currency,
                "description": l.description,
                "account_reference": l.account_reference,
                "status": l.status,
                "expires_at": l.expires_at,
                "payment_url": f"{settings.app.public_base_url}/pay/{l.public_id}",
                "created_at": l.created_at,
                "updated_at": l.updated_at,
            }
            for l in links
        ],
    }


@app.get("/payment-links/{public_id}")
def get_link(
    public_id: str,
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant_or_session),
):
    start = time.time()
    link = (
        db.query(PaymentLink)
        .filter(PaymentLink.public_id == public_id, PaymentLink.merchant_id == merchant.id)
        .first()
    )
    if not link:
        _log(db, merchant.id, "get_payment_link", 404, start)
        raise HTTPException(status_code=404, detail="Payment link not found")

    check_and_expire_link(link)
    if link.status == "EXPIRED":
        db.commit()

    _log(db, merchant.id, "get_payment_link", 200, start)
    return {
        "id": link.id,
        "public_id": link.public_id,
        "amount": link.amount,
        "currency": link.currency,
        "description": link.description,
        "account_reference": link.account_reference,
        "status": link.status,
        "expires_at": link.expires_at,
        "payment_url": f"{settings.app.public_base_url}/pay/{link.public_id}",
        "created_at": link.created_at,
        "updated_at": link.updated_at,
    }


@app.post("/payment-links/{public_id}/disable")
def disable_link(
    public_id: str,
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant_or_session),
):
    start = time.time()
    link = (
        db.query(PaymentLink)
        .filter(PaymentLink.public_id == public_id, PaymentLink.merchant_id == merchant.id)
        .first()
    )
    if not link:
        _log(db, merchant.id, "disable_payment_link", 404, start)
        raise HTTPException(status_code=404, detail="Payment link not found")

    check_and_expire_link(link)
    if link.status == "EXPIRED":
        db.commit()
        _log(db, merchant.id, "disable_payment_link", 400, start, "Link already expired")
        raise HTTPException(status_code=400, detail="Link is expired")

    try:
        link = disable_payment_link(db, link)
    except ValueError as e:
        _log(db, merchant.id, "disable_payment_link", 400, start, str(e))
        raise HTTPException(status_code=400, detail=str(e))

    _log(db, merchant.id, "disable_payment_link", 200, start)
    return {
        "id": link.id,
        "public_id": link.public_id,
        "status": link.status,
        "message": "Payment link disabled",
    }


@app.get("/pay/{public_id}")
def get_public_link(public_id: str, db: Session = Depends(get_db)):
    """Public endpoint — no auth required. Used by customers to view payment details."""
    link = db.query(PaymentLink).filter(PaymentLink.public_id == public_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Payment link not found")

    check_and_expire_link(link)
    if link.status == "EXPIRED":
        db.commit()
        raise HTTPException(status_code=410, detail="Payment link has expired")

    if link.status == "DISABLED":
        raise HTTPException(status_code=410, detail="Payment link is no longer active")

    # PAID links return their status so the frontend can display it
    return {
        "public_id": link.public_id,
        "amount": link.amount,
        "currency": link.currency,
        "description": link.description,
        "account_reference": link.account_reference,
        "status": link.status,
    }


class CustomerSTKRequest(BaseModel):
    phone: str


@app.post("/pay/{public_id}/stk")
def customer_stk_push(
    public_id: str,
    request: CustomerSTKRequest,
    db: Session = Depends(get_db),
):
    """Public endpoint — no auth required. Customer initiates STK push via payment link."""
    start = time.time()

    # Step A: Find PaymentLink
    link = db.query(PaymentLink).filter(PaymentLink.public_id == public_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Payment link not found")

    # Step B: Validate status
    check_and_expire_link(link)
    if link.status == "EXPIRED":
        db.commit()
        raise HTTPException(status_code=410, detail="Payment link has expired")

    if link.status == "PAID":
        raise HTTPException(status_code=409, detail="Payment link has already been paid")

    if link.status == "DISABLED":
        raise HTTPException(status_code=410, detail="Payment link is no longer active")

    if link.status != "ACTIVE":
        raise HTTPException(status_code=410, detail="Payment link is no longer active")

    # Step C: Validate phone
    try:
        phone = normalize_phone(request.phone)
    except ValueError as e:
        _log(db, link.merchant_id, "public_stk_push", 400, start, str(e))
        raise HTTPException(status_code=400, detail=str(e))

    # Load the merchant to get Daraja credentials
    merchant = db.query(Merchant).filter(Merchant.id == link.merchant_id).first()
    if not merchant or not merchant.daraja_shortcode:
        raise HTTPException(status_code=400, detail="Payment service not configured")

    # Step D: Create Payment (linked to PaymentLink)
    # Use payment_link_id as idempotency key to prevent duplicate submissions
    idempotency_key = f"link_{link.id}_{phone}"
    existing_payment = (
        db.query(Payment)
        .filter(
            Payment.merchant_id == link.merchant_id,
            Payment.idempotency_key == idempotency_key,
            Payment.status == "PENDING",
        )
        .first()
    )
    if existing_payment:
        # Reuse existing pending payment — don't create duplicates
        checkout_id = existing_payment.checkout_request_id
        _log(db, link.merchant_id, "public_stk_push", 200, start)
        return {
            "payment_id": existing_payment.id,
            "status": existing_payment.status,
            "message": "M-Pesa payment request sent to your phone.",
        }

    # Step E: Initiate STK via existing service
    try:
        response = stk_push(merchant, phone, link.amount, link.account_reference)
    except Exception as e:
        _log(db, link.merchant_id, "public_stk_push", 502, start, str(e))
        raise HTTPException(status_code=502, detail=f"Payment service error: {e}")

    checkout_id = response.get("CheckoutRequestID")
    payment = create_payment(
        db, phone, link.amount, checkout_id,
        merchant_id=link.merchant_id,
        payment_method="stk_push",
        idempotency_key=idempotency_key,
        payment_link_id=link.id,
    )
    _log(db, link.merchant_id, "public_stk_push", 200, start)

    # Step F: Return customer-safe response
    return {
        "payment_id": payment.id,
        "status": payment.status,
        "message": "M-Pesa payment request sent to your phone.",
    }


@app.get("/pay/{public_id}/status")
def get_payment_status(public_id: str, db: Session = Depends(get_db)):
    """Public endpoint — no auth required. Customer polls for payment status."""
    link = db.query(PaymentLink).filter(PaymentLink.public_id == public_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Payment link not found")

    # Find the most recent payment for this link
    payment = (
        db.query(Payment)
        .filter(Payment.payment_link_id == link.id)
        .order_by(Payment.created_at.desc())
        .first()
    )

    if not payment:
        return {"status": link.status}

    result = {"status": payment.status}
    if payment.status == "SUCCESS" and payment.mpesa_receipt:
        result["receipt"] = payment.mpesa_receipt
    return result
