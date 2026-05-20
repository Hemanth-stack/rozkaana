"""regional_activity_dinner

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-20 00:00:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa

revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('activity_level', sa.String(20), nullable=True))
    op.add_column('users', sa.Column('dinner_style_pref', sa.String(20), nullable=True))
    op.add_column('recipes', sa.Column('dish_category', sa.String(30), nullable=True))
    op.create_index('ix_recipes_dish_category', 'recipes', ['dish_category'])


def downgrade() -> None:
    op.drop_index('ix_recipes_dish_category', table_name='recipes')
    op.drop_column('recipes', 'dish_category')
    op.drop_column('users', 'dinner_style_pref')
    op.drop_column('users', 'activity_level')
