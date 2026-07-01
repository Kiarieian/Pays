import json
import logging
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.payment_service import update_transaction, update_disbursement_by_conversation_id

logger = logging.getLogger("daraja.callbacks")
router = APIRouter()


@router.post("/callback/{merchant_id}")
async def stk_callback(merchant_id: int, request: Request, db: Session = Depends(get_db)):
    """STK push result callback. Path includes merchant_id so we know
    which merchant's transaction this belongs to, even though Safaricom
    doesn't echo it back to us directly."""
    raw = await request.body()

    if not raw:
        logger.warning("Empty STK callback received for merchant %s", merchant_id)
        return {"ResultCode": 0, "ResultDesc": "OK"}

    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        logger.exception("Invalid JSON in STK callback for merchant %s", merchant_id)
        return {"ResultCode": 0, "ResultDesc": "OK"}

    logger.info("STK callback for merchant %s: %s", merchant_id, data)

    stk = data.get("Body", {}).get("stkCallback", {})
    checkout = stk.get("CheckoutRequestID")
    result = stk.get("ResultCode")

    receipt = None
    if result == 0:
        for item in stk.get("CallbackMetadata", {}).get("Item", []):
            if item.get("Name") == "MpesaReceiptNumber":
                receipt = item.get("Value")
        update_transaction(db, checkout, "SUCCESS", receipt)
    else:
        update_transaction(db, checkout, "FAILED", None)

    return {"ResultCode": 0, "ResultDesc": "OK"}


@router.post("/b2c/result/{merchant_id}")
async def b2c_result_callback(merchant_id: int, request: Request, db: Session = Depends(get_db)):
    """B2C disbursement result callback."""
    raw = await request.body()
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        logger.exception("Invalid JSON in B2C result callback for merchant %s", merchant_id)
        return {"ResultCode": 0, "ResultDesc": "OK"}

    logger.info("B2C result for merchant %s: %s", merchant_id, data)

    result = data.get("Result", {})
    conversation_id = result.get("ConversationID")
    result_code = result.get("ResultCode")
    result_desc = result.get("ResultDesc")

    receipt = None
    if result_code == 0:
        for item in result.get("ResultParameters", {}).get("ResultParameter", []):
            if item.get("Key") == "TransactionReceipt":
                receipt = item.get("Value")
        update_disbursement_by_conversation_id(
            db, conversation_id, "Success", receipt, result_desc
        )
    else:
        update_disbursement_by_conversation_id(
            db, conversation_id, "Failed", None, result_desc
        )

    return {"ResultCode": 0, "ResultDesc": "OK"}


@router.post("/b2c/timeout/{merchant_id}")
async def b2c_timeout_callback(merchant_id: int, request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    logger.warning("B2C timeout for merchant %s: %s", merchant_id, raw)
    return {"ResultCode": 0, "ResultDesc": "OK"}