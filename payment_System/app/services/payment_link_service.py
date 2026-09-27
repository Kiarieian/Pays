import logging
import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import PaymentLink

logger = logging.getLogger("daraja.payment_links")


def generate_public_id() -> str:
    """Generate a URL-safe public identifier for a payment link."""
    return secrets.token_urlsafe(16)


def generate_account_reference() -> str:
    """Generate a unique account reference for M-Pesa if merchant doesn't provide one."""
    return f"PL-{secrets.token_urlsafe(8)}"


def check_and_expire_link(link: PaymentLink) -> bool:
    """Check if an ACTIVE link has expired and update status if needed.
    Returns True if the link is now expired."""
    if link.status != "ACTIVE":
        return False
    if link.expires_at is None:
        return False
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if now >= link.expires_at:
        link.status = "EXPIRED"
        logger.info("Payment link %s expired (expires_at: %s)", link.public_id, link.expires_at)
        return True
    return False


def create_payment_link(
    db: Session,
    merchant_id: int,
    amount: int,
    description: str | None = None,
    account_reference: str | None = None,
    expires_at: datetime | None = None,
) -> PaymentLink:
    """Create a new payment link for a merchant."""
    public_id = generate_public_id()
    ref = account_reference if account_reference else generate_account_reference()

    link = PaymentLink(
        merchant_id=merchant_id,
        public_id=public_id,
        description=description,
        amount=amount,
        currency="KES",
        account_reference=ref,
        status="ACTIVE",
        expires_at=expires_at,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    logger.info(
        "Created payment link %s for merchant %s (amount: %s)",
        public_id, merchant_id, amount,
    )
    return link


def disable_payment_link(db: Session, link: PaymentLink) -> PaymentLink:
    """Disable an ACTIVE payment link. Only ACTIVE links can be disabled."""
    if link.status != "ACTIVE":
        raise ValueError(f"Cannot disable link in {link.status} status")
    link.status = "DISABLED"
    db.commit()
    db.refresh(link)
    logger.info("Disabled payment link %s", link.public_id)
    return link
