from app.models import Payment
from app.database import get_db

def create_payment(
    db,
    phone,
    amount,
    merchant_id,
    checkout_request_id
):

    payment = Payment(
        phone=phone,
        amount=amount,
        checkout_request_id=checkout_request_id,
        merchant_id=merchant_id,
        status="Pending"
    )

    db.add(payment)

    db.commit()

    db.refresh(payment)

    return payment
def update_transaction(
    db,
    checkout_request_id,
    status,
    mpesa_receipt=None
):

    db = next(get_db())

    payment = (
        db.query(Payment)
        .filter(
            Payment.checkout_request_id == checkout_request_id
        )
        .first()
    )

    if payment:

        payment.status = status

        if mpesa_receipt:
            payment.mpesa_receipt = mpesa_receipt

        db.commit()

        db.refresh(payment)

        return payment

    return None