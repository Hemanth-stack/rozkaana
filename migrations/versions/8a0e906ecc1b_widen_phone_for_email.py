"""widen_phone_for_email

Revision ID: 8a0e906ecc1b
Revises: 353f12fc52f3
Create Date: 2026-05-02 01:37:02.179524+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8a0e906ecc1b'
down_revision = '353f12fc52f3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('users', 'phone', type_=sa.String(254), existing_nullable=False)
    op.alter_column('otp_sessions', 'phone', type_=sa.String(254), existing_nullable=False)


def downgrade() -> None:
    op.alter_column('otp_sessions', 'phone', type_=sa.String(15), existing_nullable=False)
    op.alter_column('users', 'phone', type_=sa.String(15), existing_nullable=False)
