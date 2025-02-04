"""create staff tables

Revision ID: 20240205_create_staff_tables
Revises: 20240205_add_system_settings
Create Date: 2024-02-05 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20240205_create_staff_tables'
down_revision = '20240205_add_system_settings'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create staff table
    op.create_table('staff',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('pin', sa.String(4), nullable=False),
        sa.Column('hourly_rate', sa.Float(), server_default='0.00', nullable=False),
        sa.Column('isAdmin', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_working', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_on_break', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('available', sa.Boolean(), server_default='true', nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pin')
    )
    op.create_index(op.f('ix_staff_id'), 'staff', ['id'], unique=False)

    # Create staff_shifts table
    op.create_table('staff_shifts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('staff_id', sa.Integer(), nullable=False),
        sa.Column('clock_in', sa.DateTime(timezone=True), nullable=False),
        sa.Column('clock_out', sa.DateTime(timezone=True), nullable=True),
        sa.Column('break_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('break_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('hourly_rate', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['staff_id'], ['staff.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('staff_shifts')
    op.drop_index(op.f('ix_staff_id'), table_name='staff')
    op.drop_table('staff')
