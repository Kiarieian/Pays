"""add idempotency unique constraints

Revision ID: a1b2c3d4e5f6
Revises: 3e4307317740
Create Date: 2026-09-19 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '3e4307317740'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Partial unique index on payments: enforces uniqueness of
    # (merchant_id, idempotency_key) only when idempotency_key is NOT NULL.
    # SQLite ignores partial indexes with WHERE clauses, so this is safe
    # for both PostgreSQL (production) and SQLite (tests).
    op.create_index(
        'uq_payments_merchant_idempotency',
        'payments',
        ['merchant_id', 'idempotency_key'],
        unique=True,
        postgresql_where='idempotency_key IS NOT NULL',
    )
    op.create_index(
        'uq_disbursements_merchant_idempotency',
        'disbursements',
        ['merchant_id', 'idempotency_key'],
        unique=True,
        postgresql_where='idempotency_key IS NOT NULL',
    )


def downgrade() -> None:
    op.drop_index('uq_disbursements_merchant_idempotency', table_name='disbursements')
    op.drop_index('uq_payments_merchant_idempotency', table_name='payments')
