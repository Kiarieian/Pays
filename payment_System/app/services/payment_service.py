import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import Payment, PaymentLink, Disbursement, APIRequestLog
from app.payment_states import (
    PaymentStatus,
    DisbursementStatus,
    validate_payment_transition,
    validate_disbursement_transition,
)

logger = logging.getLogger("daraja.payments")


def create_payment(
    db: Session,
    phone: str,
    amount: int,
    checkout_request_id: str,
    merchant_id: int,
    payment_method: str = "stk_push",
    idempotency_key: str | None = None,
    payment_link_id: int | None = None,
) -> Payment:
    """Create a payment record. If idempotency_key is provided and a
    payment with that key already exists for this merchant, return
    the existing payment instead of creating a duplicate.

    The DB unique constraint on (merchant_id, idempotency_key) is the
    correctness boundary — we catch IntegrityError for concurrent races.
    """
    if idempotency_key:
        existing = (
            db.query(Payment)
            .filter(
                Payment.merchant_id == merchant_id,
                Payment.idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing:
            logger.info(
                "Idempotent hit: returning existing payment %s for key %s",
                existing.id, idempotency_key,
            )
            return existing

    payment = Payment(
        phone=phone,
        amount=amount,
        checkout_request_id=checkout_request_id,
        merchant_id=merchant_id,
        payment_method=payment_method,
        status=PaymentStatus.PENDING,
        idempotency_key=idempotency_key,
        payment_link_id=payment_link_id,
    )
    db.add(payment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.info(
            "Idempotent race: concurrent insert for merchant %s key %s — fetching existing",
            merchant_id, idempotency_key,
        )
        existing = (
            db.query(Payment)
            .filter(
                Payment.merchant_id == merchant_id,
                Payment.idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing:
            return existing
        raise
    db.refresh(payment)
    return payment


def update_transaction(
    db: Session,
    checkout_request_id: str,
    new_status: str,
    mpesa_receipt: str | None,
) -> Payment | None:
    """Update payment status with state machine validation.
    If the payment is linked to a PaymentLink, update the link status accordingly.
    Returns None if payment not found or transition is invalid."""
    payment = (
        db.query(Payment)
        .filter(Payment.checkout_request_id == checkout_request_id)
        .first()
    )
    if not payment:
        logger.warning(
            "Callback for unknown checkout_request_id: %s", checkout_request_id,
        )
        return None

    if not validate_payment_transition(payment.status, new_status):
        logger.warning(
            "Rejected transition %s -> %s for payment %s (checkout: %s)",
            payment.status, new_status, payment.id, checkout_request_id,
        )
        return payment  # Return without changing state

    payment.status = new_status
    payment.mpesa_receipt = mpesa_receipt

    # If this payment is linked to a PaymentLink, update the link status
    if payment.payment_link_id and new_status == PaymentStatus.SUCCESS:
        link = db.query(PaymentLink).filter(PaymentLink.id == payment.payment_link_id).first()
        if link and link.status == "ACTIVE":
            link.status = "PAID"
            logger.info(
                "PaymentLink %s -> PAID (payment %s succeeded)",
                link.public_id, payment.id,
            )

    db.commit()
    db.refresh(payment)
    logger.info(
        "Payment %s: %s -> %s (receipt: %s)",
        payment.id, payment.status if payment.status != new_status else "PENDING", new_status, mpesa_receipt,
    )
    return payment


def create_disbursement(
    db: Session,
    merchant_id: int,
    phone: str,
    amount: int,
    remarks: str,
    conversation_id: str | None = None,
    originator_conversation_id: str | None = None,
    idempotency_key: str | None = None,
) -> Disbursement:
    """Create a disbursement record with optional idempotency.
    DB unique constraint is the correctness boundary for concurrent races."""
    if idempotency_key:
        existing = (
            db.query(Disbursement)
            .filter(
                Disbursement.merchant_id == merchant_id,
                Disbursement.idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing:
            logger.info(
                "Idempotent hit: returning existing disbursement %s for key %s",
                existing.id, idempotency_key,
            )
            return existing

    disbursement = Disbursement(
        merchant_id=merchant_id,
        phone=phone,
        amount=amount,
        remarks=remarks,
        conversation_id=conversation_id,
        originator_conversation_id=originator_conversation_id,
        status=DisbursementStatus.PENDING,
        idempotency_key=idempotency_key,
    )
    db.add(disbursement)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.info(
            "Idempotent race: concurrent insert for merchant %s key %s — fetching existing",
            merchant_id, idempotency_key,
        )
        existing = (
            db.query(Disbursement)
            .filter(
                Disbursement.merchant_id == merchant_id,
                Disbursement.idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing:
            return existing
        raise
    db.refresh(disbursement)
    return disbursement


def update_disbursement_by_conversation_id(
    db: Session,
    conversation_id: str,
    new_status: str,
    mpesa_receipt: str | None = None,
    result_desc: str | None = None,
) -> Disbursement | None:
    """Update disbursement status with state machine validation."""
    disbursement = (
        db.query(Disbursement)
        .filter(Disbursement.conversation_id == conversation_id)
        .first()
    )
    if not disbursement:
        logger.warning(
            "Callback for unknown conversation_id: %s", conversation_id,
        )
        return None

    if not validate_disbursement_transition(disbursement.status, new_status):
        logger.warning(
            "Rejected transition %s -> %s for disbursement %s (conv: %s)",
            disbursement.status, new_status, disbursement.id, conversation_id,
        )
        return disbursement

    disbursement.status = new_status
    disbursement.mpesa_receipt = mpesa_receipt
    disbursement.result_desc = result_desc
    disbursement.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(disbursement)
    logger.info(
        "Disbursement %s: -> %s (receipt: %s)",
        disbursement.id, new_status, mpesa_receipt,
    )
    return disbursement


def log_api_request(
    db: Session,
    merchant_id: int,
    endpoint: str,
    status_code: int,
    response_time_ms: int | None = None,
    error_message: str | None = None,
    request_id: str | None = None,
) -> APIRequestLog:
    log = APIRequestLog(
        merchant_id=merchant_id,
        endpoint=endpoint,
        status_code=status_code,
        response_time_ms=response_time_ms,
        error_message=error_message,
        request_id=request_id,
    )
    db.add(log)
    db.commit()
    return log
