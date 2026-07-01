from sqlalchemy.orm import Session
from app.models import Merchant
import uuid

def create_merchant(db: Session, name: str, email: str, phone: str):
    existing = (
        db.query(Merchant)
        .filter(Merchant.email == email)
        .first()
    )
    if existing:
        return ValueError("This email already exists.")
    
    merchant = Merchant(
        business_name=name,
        email=email,
        phone=phone,
        api_key=uuid.uuid4().hex
    )
    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    
    return merchant

def get_merchant(db: Session, merchant_id: int):
    return db.query(Merchant).filter(Merchant.id == merchant_id).first()


def get_merchant_by_api_key(db: Session, api_key: str):
    return db.query(Merchant).filter(Merchant.api_key == api_key).first()
