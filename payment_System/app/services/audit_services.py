import json

from app.models import AuditLog
from datetime import datetime


def log_event(
    db,
    event_type: str,
    reference_id: str = None,
    merchant_id: int = None,
    metadata: dict = None,
    ip_address: str = None
):
    log = AuditLog(
        event_type=event_type,
        reference_id=reference_id,
        merchant_id=merchant_id,
        metadata=json.dumps(metadata or {}),
        ip_address=ip_address,
        created_at=datetime.utcnow()
    )

    db.add(log)
    db.commit()