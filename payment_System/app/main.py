from fastapi import FastAPI
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from fastapi import Request

from app.database import get_db
from app.services.payment_service import create_payment, update_transaction

from pydantic import BaseModel
from app.daraja import get_access_token
from app.daraja import stk_push
from app.daraja import generate_qr
from app.callbacks import router as callback_router
import requests
import uuid

from app.models import Payment, Merchant
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()
app.include_router(callback_router, prefix="/api/payment")
class PaymentRequest(BaseModel):
    phone: str
    amount: int

@app.get("/")
def home():
    return {"message": "Kiarie Payment System Running"}

@app.get("/token")
def token():
    token = get_access_token()

    return {
        "access_token": token
    }
@app.get("/payments")
def get_payments(
    db: Session = Depends(get_db)
):

    payments = db.query(Payment).all()

    return [
        {
            "id": payment.id,
            "phone": payment.phone,
            "amount": payment.amount,
            "status": payment.status,
            "checkout_request_id": payment.checkout_request_id,
            "mpesa_receipt": payment.mpesa_receipt,
            "created_at": payment.created_at
        }
        for payment in payments
    ]
def get_current_merchant(
    x_api_key: str = Header(...),
    db: Session = Depends(get_db)
):
    merchant = db.query(Merchant).filter(Merchant.api_key == x_api_key).first()

    if not merchant:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if merchant.status != "active":
        raise HTTPException(status_code=403, detail="Merchant inactive")

    return merchant
@app.post("/pay")
async def pay(request: PaymentRequest, db: Session = Depends(get_db), merchant: Merchant = Depends(get_current_merchant)):
    response = stk_push(
        request.phone,
        request.amount
        )
    checkout_id = response.get("CheckoutRequestID")

    payment = create_payment(
        db,
        request.phone,
        request.amount,
        request.checkout_request_id,
        merchant.id
    )

    return {
        "payment_id": payment.id,
        "checkout_id": checkout_id,
        "status": payment.status
    }
@app.get("/generate_qr")
def generate_qr_code():

    account_ref = str(uuid.uuid4())
    qr_data = {
        "amount": 100,
        "account_ref": account_ref
    }
    
    return {
        "account_ref": account_ref,
        "qr_data": qr_data
    }

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175"],  # dev url or frontend url
    allow_methods=["*"],
    allow_headers=["*"],
)