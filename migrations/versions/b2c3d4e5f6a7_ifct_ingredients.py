"""ifct_ingredients table + pg_trgm extension

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

    op.create_table(
        'ifct_ingredients',
        sa.Column('id', postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('aliases', postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'::varchar[]")),
        sa.Column('food_group', sa.String(50), nullable=True),
        sa.Column('calories_per_100g', sa.Numeric(7, 2), nullable=True),
        sa.Column('protein_g', sa.Numeric(6, 3), nullable=True),
        sa.Column('carbs_g', sa.Numeric(6, 3), nullable=True),
        sa.Column('fat_g', sa.Numeric(6, 3), nullable=True),
        sa.Column('fibre_g', sa.Numeric(6, 3), nullable=True),
        sa.Column('sugar_g', sa.Numeric(6, 3), nullable=True),
        sa.Column('sodium_mg', sa.Numeric(8, 2), nullable=True),
        sa.Column('potassium_mg', sa.Numeric(8, 2), nullable=True),
        sa.Column('iron_mg', sa.Numeric(7, 3), nullable=True),
        sa.Column('calcium_mg', sa.Numeric(8, 2), nullable=True),
        sa.Column('vitamin_c_mg', sa.Numeric(7, 3), nullable=True),
        sa.Column('vitamin_b12_mcg', sa.Numeric(6, 3), nullable=True),
        sa.Column('vitamin_d_mcg', sa.Numeric(6, 3), nullable=True),
        sa.Column('water_g', sa.Numeric(6, 2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint('name', name='uq_ifct_name'),
    )

    op.create_index(
        'ix_ifct_name_trgm',
        'ifct_ingredients',
        ['name'],
        postgresql_using='gin',
        postgresql_ops={'name': 'gin_trgm_ops'},
    )
    op.create_index(
        'ix_ifct_aliases',
        'ifct_ingredients',
        ['aliases'],
        postgresql_using='gin',
    )


def downgrade() -> None:
    op.drop_index('ix_ifct_aliases', table_name='ifct_ingredients')
    op.drop_index('ix_ifct_name_trgm', table_name='ifct_ingredients')
    op.drop_table('ifct_ingredients')
