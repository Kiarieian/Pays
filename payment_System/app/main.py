import logging
import time
import uuid

<<<<<<< HEAD
from app.models import Payment, Merchant
from fastapi.middleware.cors import CORSMiddleware
=======
from fastapi import FastAPI, Header, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
>>>>>>> e70dff8 (Replace payment_System with payment_system and update backend)

from app.database import get_db, engine
from app.models import Base, Merchant, Payment
from app.services.payment_service import create_payment, create_disbursement, log_api_request
from app.security import generate_api_key, verify_api_key
from app.daraja import stk_push, generate_qr, b2c_disbursement, normalize_phone
from app.callbacks import router as callback_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("daraja.main")

Base.metadata.create_all(bind=engine)

app = FastAPI(title="M-Pesa Daraja Gateway")
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
    environment: str = "sandbox"  # "sandbox" | "production"


class B2CCredentialsRequest(BaseModel):
    shortcode: str
    initiator_name: str
    security_credential: str  # pre-encrypted per Safaricom's spec


class PaymentRequest(BaseModel):
    phone: str
    amount: int
    account_reference: str | None = None


class QRRequest(BaseModel):
    amount: int
    account_reference: str
    trx_code: str = "BG"  # BG=buy goods, PB=paybill, SM=send money


class DisbursementRequest(BaseModel):
    phone: str
    amount: int
    remarks: str = "Disbursement"


# ---------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------
def get_current_merchant(
    x_api_key: str = Header(...),
    db: Session = Depends(get_db),
) -> Merchant:
    if len(x_api_key) < 12:
        raise HTTPException(status_code=401, detail="Invalid API key")

    prefix = x_api_key[:12]
    merchant = db.query(Merchant).filter(Merchant.api_key_prefix == prefix).first()

    if not merchant or not merchant.api_key_hash or not verify_api_key(x_api_key, merchant.api_key_hash):
        raise HTTPException(status_code=401, detail="Invalid API key")

    if merchant.status != "active":
        raise HTTPException(status_code=403, detail=f"Merchant account is {merchant.status}")

    return merchant

<<<<<<< HEAD
    payment = create_payment(
        db,
        request.phone,
        request.amount,
        request.checkout_request_id,
        merchant.id
=======

def _log(db: Session, merchant_id, endpoint, status_code, start_time, error=None):
    elapsed_ms = int((time.time() - start_time) * 1000)
    try:
        log_api_request(db, merchant_id, endpoint, status_code, elapsed_ms, error)
    except Exception:
        logger.exception("Failed to write API request log")


# ---------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------
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
        status="pending",  # flip to "active" after you verify them (manual or automated)
>>>>>>> e70dff8 (Replace payment_System with payment_system and update backend)
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
        "api_key": raw_key,  # shown ONCE — merchant must save this now
        "message": "Save this API key now — it will not be shown again. "
                   "Your account is pending activation.",
    }


@app.post("/merchants/daraja-credentials")
def submit_daraja_credentials(
    request: DarajaCredentialsRequest,
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant),
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
    merchant: Merchant = Depends(get_current_merchant),
):

    merchant.set_b2c_credentials(
        shortcode=request.shortcode,
        initiator_name=request.initiator_name,
        security_credential=request.security_credential,
    )
    db.commit()
    return {"message": "B2C credentials saved"}


@app.get("/merchants/me")
def get_merchant_profile(merchant: Merchant = Depends(get_current_merchant)):
    return {
        "id": merchant.id,
        "business_name": merchant.business_name,
        "email": merchant.email,
        "status": merchant.status,
        "daraja_configured": bool(merchant.daraja_shortcode),
        "b2c_configured": merchant.has_b2c_credentials(),
    }


# ---------------------------------------------------------------------
# STK Push
# ---------------------------------------------------------------------
@app.post("/pay")
def pay(
    request: PaymentRequest,
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant),
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
    )
    _log(db, merchant.id, "stk_push", 200, start)

    return {
        "payment_id": payment.id,
        "checkout_id": checkout_id,
        "status": payment.status,
    }


# ---------------------------------------------------------------------
# QR Code generation — now actually calls Daraja and requires auth
# ---------------------------------------------------------------------
@app.post("/generate_qr")
def generate_qr_code(
    request: QRRequest,
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant),
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

<<<<<<< HEAD
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175"],  # dev url or frontend url
    allow_methods=["*"],
    allow_headers=["*"],
)
=======

# ---------------------------------------------------------------------
# B2C Disbursement — always uses the MERCHANT's own B2C credentials.
# Money moves merchant -> customer directly; we never hold these funds.
# ---------------------------------------------------------------------
@app.post("/disburse")
def disburse(
    request: DisbursementRequest,
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant),
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
    )
    _log(db, merchant.id, "disburse", 200, start)

    return {
        "disbursement_id": disbursement.id,
        "conversation_id": conversation_id,
        "status": disbursement.status,
    }


# ---------------------------------------------------------------------
# Dashboard-style endpoints (usage / API tracking)
# ---------------------------------------------------------------------
@app.get("/payments")
def get_payments(
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant),
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


from app.models import APIRequestLog  # noqa: E402


@app.get("/usage")
def get_usage(
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant),
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
>>>>>>> e70dff8 (Replace payment_System with payment_system and update backend)
