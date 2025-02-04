"""add system settings

Revision ID: 20240205_add_system_settings
Revises: 
Create Date: 2024-02-05 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20240205_add_system_settings'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create system_settings table
    op.create_table('system_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('last_order_reset', sa.DateTime(timezone=True), nullable=True),
        sa.Column('timezone', sa.String(), server_default='America/Los_Angeles', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    # Drop system_settings table
    op.drop_table('system_settings') 