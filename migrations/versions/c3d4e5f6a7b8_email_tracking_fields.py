"""add email_sent_at and email_status to daily_menus

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-09 00:00:00.000000+00:00

Separates email delivery tracking from WhatsApp delivery tracking.
Previously both shared wa_sent_at / wa_status, which caused confusion
and would break once WhatsApp is re-enabled alongside emails.
"""
from alembic import op
import sqlalchemy as sa


revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('daily_menus', sa.Column(
        'email_sent_at', sa.DateTime(timezone=True), nullable=True
    ))
    op.add_column('daily_menus', sa.Column(
        'email_status', sa.String(length=20),
        server_default='pending', nullable=True
    ))
    # Back-fill: any menu that was already "sent" via wa_sent_at was actually an email send.
    op.execute("""
        UPDATE daily_menus
        SET email_sent_at = wa_sent_at,
            email_status  = CASE WHEN wa_status = 'sent' THEN 'sent' ELSE wa_status END
        WHERE wa_sent_at IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_column('daily_menus', 'email_status')
    op.drop_column('daily_menus', 'email_sent_at')
