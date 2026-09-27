"""rebuild payment_links with public_id, status, expiration; add payment_link_id to payments

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old unused payment_links table (was never routed, no data)
    op.drop_index('ix_payment_links_slug', table_name='payment_links')
    op.drop_index('ix_payment_links_merchant_id', table_name='payment_links')
    op.drop_index('ix_payment_links_id', table_name='payment_links')
    op.drop_table('payment_links')

    # Create new payment_links table
    op.create_table('payment_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('merchant_id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(), nullable=False, server_default='KES'),
        sa.Column('account_reference', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='ACTIVE'),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_id'),
    )
    op.create_index('ix_payment_links_id', 'payment_links', ['id'], unique=False)
    op.create_index('ix_payment_links_public_id', 'payment_links', ['public_id'], unique=True)
    op.create_index('ix_payment_links_merchant_id', 'payment_links', ['merchant_id'], unique=False)
    op.create_index('ix_payment_links_status', 'payment_links', ['status'], unique=False)
    op.create_index('ix_payment_links_merchant_status', 'payment_links', ['merchant_id', 'status'], unique=False)
    op.create_index('ix_payment_links_merchant_created', 'payment_links', ['merchant_id', 'created_at'], unique=False)

    # Add payment_link_id to payments table
    op.add_column('payments', sa.Column('payment_link_id', sa.Integer(), nullable=True))
    op.create_index('ix_payments_payment_link_id', 'payments', ['payment_link_id'], unique=False)
    op.create_foreign_key('fk_payments_payment_link_id', 'payments', 'payment_links', ['payment_link_id'], ['id'])


def downgrade() -> None:
    # Remove payment_link_id from payments
    op.drop_constraint('fk_payments_payment_link_id', 'payments', type_='foreignkey')
    op.drop_index('ix_payments_payment_link_id', table_name='payments')
    op.drop_column('payments', 'payment_link_id')

    # Drop new payment_links table
    op.drop_index('ix_payment_links_merchant_created', table_name='payment_links')
    op.drop_index('ix_payment_links_merchant_status', table_name='payment_links')
    op.drop_index('ix_payment_links_status', table_name='payment_links')
    op.drop_index('ix_payment_links_merchant_id', table_name='payment_links')
    op.drop_index('ix_payment_links_public_id', table_name='payment_links')
    op.drop_index('ix_payment_links_id', table_name='payment_links')
    op.drop_table('payment_links')

    # Recreate old payment_links table
    op.create_table('payment_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('merchant_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )
    op.create_index('ix_payment_links_id', 'payment_links', ['id'], unique=False)
    op.create_index('ix_payment_links_merchant_id', 'payment_links', ['merchant_id'], unique=False)
    op.create_index('ix_payment_links_slug', 'payment_links', ['slug'], unique=True)
