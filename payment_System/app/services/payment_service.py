from datetime import datetime
from sqlalchemy.orm import Session

from app.models import Payment, Disbursement, APIRequestLog


def create_payment(db: Session, phone, amount, checkout_request_id,
                    merchant_id, payment_method="stk_push"):
    payment = Payment(
        phone=phone,
        amount=amount,
        checkout_request_id=checkout_request_id,
        merchant_id=merchant_id,
        payment_method=payment_method,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def update_transaction(db: Session, checkout_request_id, status, mpesa_receipt):
    payment = (
        db.query(Payment)
        .filter(Payment.checkout_request_id == checkout_request_id)
        .first()
    )
    if not payment:
        return None
    payment.status = status
    payment.mpesa_receipt = mpesa_receipt
    db.commit()
    db.refresh(payment)
    return payment


def create_disbursement(db: Session, merchant_id, phone, amount, remarks,
                         conversation_id=None, originator_conversation_id=None):
    disbursement = Disbursement(
        merchant_id=merchant_id,
        phone=phone,
        amount=amount,
        remarks=remarks,
        conversation_id=conversation_id,
        originator_conversation_id=originator_conversation_id,
    )
    db.add(disbursement)
    db.commit()
    db.refresh(disbursement)
    return disbursement


def update_disbursement_by_conversation_id(db: Session, conversation_id, status,
                                            mpesa_receipt=None, result_desc=None):
    disbursement = (
        db.query(Disbursement)
        .filter(Disbursement.conversation_id == conversation_id)
        .first()
    )
    if not disbursement:
        return None
    disbursement.status = status
    disbursement.mpesa_receipt = mpesa_receipt
    disbursement.result_desc = result_desc
    disbursement.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(disbursement)
    return disbursement


def log_api_request(db: Session, merchant_id, endpoint, status_code,
                     response_time_ms=None, error_message=None):
    log = APIRequestLog(
        merchant_id=merchant_id,
        endpoint=endpoint,
        status_code=status_code,
        response_time_ms=response_time_ms,
        error_message=error_message,
    )
    db.add(log)
    db.commit()
    return log