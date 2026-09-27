"""Create all tables. Used only for initial setup / development.
In production, use Alembic migrations instead."""
from app.database import engine, Base
from app.models import Merchant, Payment, Disbursement, PaymentLink, APIRequestLog  # noqa: F401

Base.metadata.create_all(bind=engine)
print("Tables created successfully")
