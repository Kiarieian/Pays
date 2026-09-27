"""add password_hash and merchant_sessions for browser auth

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-19 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add password_hash column to merchants (nullable — existing merchants have no password yet)
    op.add_column('merchants', sa.Column('password_hash', sa.String(), nullable=True))

    # Create merchant_sessions table for browser/dashboard session auth
    op.create_table(
        'merchant_sessions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('merchant_id', sa.Integer(), sa.ForeignKey('merchants.id'), nullable=False),
        sa.Column('token_hash', sa.String(), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
    )
    op.create_index('ix_merchant_sessions_merchant_id', 'merchant_sessions', ['merchant_id'])
    op.create_index('ix_merchant_sessions_token_hash', 'merchant_sessions', ['token_hash'], unique=True)


def downgrade() -> None:
    op.drop_table('merchant_sessions')
    op.drop_column('merchants', 'password_hash')
