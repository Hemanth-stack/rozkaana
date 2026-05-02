"""micronutrients_indexes_signals

Revision ID: a1b2c3d4e5f6
Revises: 8a0e906ecc1b
Create Date: 2026-05-02 14:00:00.000000+00:00

Adds:
- Micronutrient columns to recipes table (sodium, iron, calcium, B12, vitamin C/D, glycemic_index, sugar_g, potassium_mg)
- Performance indexes on daily_menus (owner_id, menu_date)
- user_nutrition_signals table for daily health signal tracking
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID


revision = 'a1b2c3d4e5f6'
down_revision = '8a0e906ecc1b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Recipe micronutrients ──────────────────────────────────────────────────
    op.add_column('recipes', sa.Column('sugar_g',        sa.Numeric(5, 2), nullable=True))
    op.add_column('recipes', sa.Column('sodium_mg',      sa.Numeric(7, 1), nullable=True))
    op.add_column('recipes', sa.Column('potassium_mg',   sa.Numeric(7, 1), nullable=True))
    op.add_column('recipes', sa.Column('iron_mg',        sa.Numeric(6, 2), nullable=True))
    op.add_column('recipes', sa.Column('calcium_mg',     sa.Numeric(7, 1), nullable=True))
    op.add_column('recipes', sa.Column('vitamin_c_mg',   sa.Numeric(6, 2), nullable=True))
    op.add_column('recipes', sa.Column('vitamin_b12_mcg',sa.Numeric(5, 2), nullable=True))
    op.add_column('recipes', sa.Column('vitamin_d_mcg',  sa.Numeric(5, 2), nullable=True))
    op.add_column('recipes', sa.Column('glycemic_index', sa.SmallInteger(),nullable=True))

    # ── Performance indexes on daily_menus ────────────────────────────────────
    op.create_index('ix_daily_menus_owner_id',   'daily_menus', ['owner_id'],          if_not_exists=True)
    op.create_index('ix_daily_menus_menu_date',  'daily_menus', ['menu_date'],         if_not_exists=True)
    op.create_index('ix_daily_menus_owner_date', 'daily_menus', ['owner_id','menu_date'], if_not_exists=True)

    # ── user_nutrition_signals table ──────────────────────────────────────────
    op.create_table(
        'user_nutrition_signals',
        sa.Column('id',                  UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id',             UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('signal_date',         sa.Date(), nullable=False,
                  server_default=sa.text('CURRENT_DATE')),
        sa.Column('energy_level',        sa.SmallInteger(), nullable=True),
        sa.Column('hunger_rating',       sa.SmallInteger(), nullable=True),
        sa.Column('digestion_comfort',   sa.SmallInteger(), nullable=True),
        sa.Column('sleep_quality',       sa.SmallInteger(), nullable=True),
        sa.Column('sleep_hours',         sa.Numeric(3, 1),  nullable=True),
        sa.Column('mood',                sa.String(20),     nullable=True),
        sa.Column('focus_level',         sa.SmallInteger(), nullable=True),
        sa.Column('blood_sugar_dip',     sa.Boolean(),      nullable=True),
        sa.Column('muscle_cramps',       sa.Boolean(),      nullable=True),
        sa.Column('hair_loss_noticed',   sa.Boolean(),      nullable=True),
        sa.Column('weight_kg',           sa.Numeric(5, 2),  nullable=True),
        sa.Column('blood_glucose_mg_dl', sa.SmallInteger(), nullable=True),
        sa.Column('followed_menu',       sa.Boolean(),      nullable=True),
        sa.Column('skipped_slots',       ARRAY(sa.String()), nullable=True),
        sa.Column('notes',               sa.String(500),    nullable=True),
        sa.Column('created_at',          sa.DateTime(timezone=True),
                  server_default=sa.text('now()')),
    )
    op.create_index('ix_uns_user_id',   'user_nutrition_signals', ['user_id'])
    op.create_index('ix_uns_date',      'user_nutrition_signals', ['signal_date'])
    op.create_index('ix_uns_user_date', 'user_nutrition_signals', ['user_id', 'signal_date'])
    # Unique constraint prevents race-condition duplicate entries for the same day
    op.create_unique_constraint(
        'uq_uns_user_date', 'user_nutrition_signals', ['user_id', 'signal_date']
    )


def downgrade() -> None:
    op.drop_constraint('uq_uns_user_date', 'user_nutrition_signals')
    op.drop_table('user_nutrition_signals')
    op.drop_index('ix_daily_menus_owner_date', table_name='daily_menus')
    op.drop_index('ix_daily_menus_menu_date',  table_name='daily_menus')
    op.drop_index('ix_daily_menus_owner_id',   table_name='daily_menus')
    for col in ['glycemic_index', 'vitamin_d_mcg', 'vitamin_b12_mcg',
                'vitamin_c_mg', 'calcium_mg', 'iron_mg', 'potassium_mg',
                'sodium_mg', 'sugar_g']:
        op.drop_column('recipes', col)
