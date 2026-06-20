import json
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.payment_service import update_transaction

router = APIRouter()

@router.post("/callback")
async def callback(request: Request, db: Session = Depends(get_db)):

    raw = await request.body()

    if not raw:
        print("⚠️ Empty callback ignored")
        return {"ResultCode": 0, "ResultDesc": "OK"}

    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        print("❌ Invalid JSON:", e)
        return {"ResultCode": 0, "ResultDesc": "OK"}

    print("✅ CALLBACK:", data)

    stk = data.get("Body", {}).get("stkCallback", {})

    checkout = stk.get("CheckoutRequestID")
    result = stk.get("ResultCode")

    receipt = None

    if result == 0:
        for i in stk.get("CallbackMetadata", {}).get("Item", []):
            if i.get("Name") == "MpesaReceiptNumber":
                receipt = i.get("Value")

        update_transaction(db, checkout, "SUCCESS", receipt)
    else:
        update_transaction(db, checkout, "FAILED", None)

    return {"ResultCode": 0, "ResultDesc": "OK"}