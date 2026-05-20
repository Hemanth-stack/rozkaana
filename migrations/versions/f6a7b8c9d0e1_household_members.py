"""household_members

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-20 00:00:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── households: add adult/child count columns ────────────────────────────
    op.add_column('households', sa.Column('adult_count', sa.SmallInteger(), server_default='0', nullable=True))
    op.add_column('households', sa.Column('child_count', sa.SmallInteger(), server_default='0', nullable=True))

    # ── household_members ────────────────────────────────────────────────────
    op.create_table(
        'household_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('household_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('linked_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('member_type', sa.String(10), nullable=False),   # adult/teen/child/infant/senior
        sa.Column('age', sa.SmallInteger(), nullable=True),
        sa.Column('gender', sa.String(10), nullable=True),
        sa.Column('weight_kg', sa.Numeric(5, 2), nullable=True),
        sa.Column('height_cm', sa.Numeric(5, 2), nullable=True),
        sa.Column('bmi', sa.Numeric(4, 2), nullable=True),
        sa.Column('bmi_band', sa.String(20), nullable=True),
        sa.Column('eating_mode', sa.String(20), nullable=True),
        sa.Column('activity_level', sa.String(20), nullable=True),
        sa.Column('health_tags', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('allergy_tags', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('goal', sa.String(20), nullable=True),
        sa.Column('daily_calorie_target', sa.SmallInteger(), nullable=True),
        sa.Column('daily_protein_target_g', sa.Numeric(5, 1), nullable=True),
        sa.Column('daily_carbs_target_g', sa.Numeric(5, 1), nullable=True),
        sa.Column('daily_fat_target_g', sa.Numeric(5, 1), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['household_id'], ['households.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['linked_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_hm_household_id', 'household_members', ['household_id'])
    op.create_index('ix_hm_linked_user_id', 'household_members', ['linked_user_id'])
    op.create_index('ix_hm_health_tags', 'household_members', ['health_tags'], postgresql_using='gin')
    op.create_index('ix_hm_allergy_tags', 'household_members', ['allergy_tags'], postgresql_using='gin')

    # ── household_member_signals ─────────────────────────────────────────────
    op.create_table(
        'household_member_signals',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('member_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('signal_date', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=False),
        sa.Column('energy_level', sa.SmallInteger(), nullable=True),
        sa.Column('hunger_rating', sa.SmallInteger(), nullable=True),
        sa.Column('digestion_comfort', sa.SmallInteger(), nullable=True),
        sa.Column('sleep_quality', sa.SmallInteger(), nullable=True),
        sa.Column('sleep_hours', sa.Numeric(3, 1), nullable=True),
        sa.Column('mood', sa.String(20), nullable=True),
        sa.Column('focus_level', sa.SmallInteger(), nullable=True),
        sa.Column('blood_sugar_dip', sa.Boolean(), nullable=True),
        sa.Column('muscle_cramps', sa.Boolean(), nullable=True),
        sa.Column('hair_loss_noticed', sa.Boolean(), nullable=True),
        sa.Column('weight_kg', sa.Numeric(5, 2), nullable=True),
        sa.Column('blood_glucose_mg_dl', sa.SmallInteger(), nullable=True),
        sa.Column('followed_menu', sa.Boolean(), nullable=True),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['member_id'], ['household_members.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('member_id', 'signal_date', name='uq_hms_member_date'),
    )
    op.create_index('ix_hms_member_id', 'household_member_signals', ['member_id'])
    op.create_index('ix_hms_signal_date', 'household_member_signals', ['signal_date'])


def downgrade() -> None:
    op.drop_index('ix_hms_signal_date', table_name='household_member_signals')
    op.drop_index('ix_hms_member_id', table_name='household_member_signals')
    op.drop_table('household_member_signals')
    op.drop_index('ix_hm_allergy_tags', table_name='household_members')
    op.drop_index('ix_hm_health_tags', table_name='household_members')
    op.drop_index('ix_hm_linked_user_id', table_name='household_members')
    op.drop_index('ix_hm_household_id', table_name='household_members')
    op.drop_table('household_members')
    op.drop_column('households', 'child_count')
    op.drop_column('households', 'adult_count')
