from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

from app.database import Base
import secrets


class Payment(Base):
        
    __tablename__ = "payments"


    id = Column(Integer, primary_key=True, index=True)

    merchant_id = Column(Integer, nullable=False)

    phone = Column(String, nullable=False)

    amount = Column(Integer, nullable=False)

    payment_method = Column(String, nullable=False)

    status = Column(String, default="Pending")

    checkout_request_id = Column(
        String,
        unique=True,
        nullable=True
    )

    mpesa_receipt = Column(
        String,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )
    def __init__(
        self,
        phone,
        amount,
        checkout_request_id,
        status="Pending",
        mpesa_receipt=None,
        merchant_id=None
    ):
        self.phone = phone
        self.amount = amount
        self.checkout_request_id = checkout_request_id
        self.status = status
        self.mpesa_receipt = mpesa_receipt
        self.merchant_id = merchant_id

class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(Integer, primary_key=True, index=True)

    business_name = Column(String, nullable=False)

    email = Column(String, unique=True, nullable=False)

    phone = Column(String, unique=True, nullable=False)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )
    def __init__(self, name, email, phone):
        self.business_name = name
        self.email = email
        self.api_key = api_key
        self.phone = phone
