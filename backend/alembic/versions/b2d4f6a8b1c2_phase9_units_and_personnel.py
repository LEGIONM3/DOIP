"""phase9_units_and_personnel

Revision ID: b2d4f6a8b1c2
Revises: a1c3e5f7a9b0
Create Date: 2026-10-13 21:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b2d4f6a8b1c2'
down_revision: Union[str, Sequence[str], None] = 'a1c3e5f7a9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to include persistent unit and personnel models."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'units' not in existing_tables:
        op.create_table(
            'units',
            sa.Column('id', sa.String(length=64), primary_key=True),
            sa.Column('run_id', sa.String(length=64), nullable=True, index=True),
            sa.Column('callsign', sa.String(length=64), nullable=False),
            sa.Column('kind', sa.String(length=32), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
            sa.Column('lat', sa.Float(), nullable=False),
            sa.Column('lon', sa.Float(), nullable=False),
            sa.Column('heading', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('speed_kph', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('fuel', sa.Float(), nullable=False, server_default='100.0'),
            sa.Column('battery', sa.Float(), nullable=False, server_default='100.0'),
            sa.Column('sector', sa.String(length=16), nullable=False, server_default='A'),
            sa.Column('route_json', sa.JSON(), nullable=False),
            sa.Column('active_mission_id', sa.String(length=64), nullable=True),
            sa.Column('last_seen_tick', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        )

    if 'unit_position_history' not in existing_tables:
        op.create_table(
            'unit_position_history',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('run_id', sa.String(length=64), nullable=False, index=True),
            sa.Column('unit_id', sa.String(length=64), nullable=False, index=True),
            sa.Column('tick', sa.Integer(), nullable=False, index=True),
            sa.Column('sim_time', sa.Integer(), nullable=False),
            sa.Column('lat', sa.Float(), nullable=False),
            sa.Column('lon', sa.Float(), nullable=False),
            sa.Column('heading', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('speed_kph', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('in_weather', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        )

    if 'personnel' not in existing_tables:
        op.create_table(
            'personnel',
            sa.Column('id', sa.String(length=64), primary_key=True),
            sa.Column('run_id', sa.String(length=64), nullable=True, index=True),
            sa.Column('name', sa.String(length=128), nullable=False),
            sa.Column('rank', sa.String(length=32), nullable=False),
            sa.Column('unit_id', sa.String(length=64), nullable=False, index=True),
            sa.Column('condition', sa.String(length=32), nullable=False, server_default='fit'),
            sa.Column('heart_rate', sa.Float(), nullable=False, server_default='72.0'),
            sa.Column('fatigue', sa.Float(), nullable=False, server_default='0.20'),
            sa.Column('active_mission_id', sa.String(length=64), nullable=True),
            sa.Column('mission_history_json', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        )

    if 'personnel_vitals_history' not in existing_tables:
        op.create_table(
            'personnel_vitals_history',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('run_id', sa.String(length=64), nullable=False, index=True),
            sa.Column('person_id', sa.String(length=64), nullable=False, index=True),
            sa.Column('tick', sa.Integer(), nullable=False, index=True),
            sa.Column('sim_time', sa.Integer(), nullable=False),
            sa.Column('heart_rate', sa.Float(), nullable=False),
            sa.Column('fatigue', sa.Float(), nullable=False),
            sa.Column('activity_type', sa.String(length=32), nullable=False, server_default='patrol'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        )

    if 'personnel_assignments' not in existing_tables:
        op.create_table(
            'personnel_assignments',
            sa.Column('id', sa.String(length=64), primary_key=True),
            sa.Column('run_id', sa.String(length=64), nullable=False, index=True),
            sa.Column('person_id', sa.String(length=64), nullable=False, index=True),
            sa.Column('unit_id', sa.String(length=64), nullable=False, index=True),
            sa.Column('mission_id', sa.String(length=64), nullable=True),
            sa.Column('role', sa.String(length=64), nullable=False, server_default='operator'),
            sa.Column('assigned_at_tick', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        )


def downgrade() -> None:
    op.drop_table('personnel_assignments')
    op.drop_table('personnel_vitals_history')
    op.drop_table('personnel')
    op.drop_table('unit_position_history')
    op.drop_table('units')
