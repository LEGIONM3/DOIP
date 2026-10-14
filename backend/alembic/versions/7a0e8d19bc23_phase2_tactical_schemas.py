"""phase2_tactical_schemas

Revision ID: 7a0e8d19bc23
Revises: 60bd2854aa56
Create Date: 2026-10-01 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.models


# revision identifiers, used by Alembic.
revision: str = '7a0e8d19bc23'
down_revision: Union[str, Sequence[str], None] = '60bd2854aa56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to include Phase 2 tactical planning tables."""
    # 1. missions
    op.create_table(
        'missions',
        sa.Column('id', sa.String(length=64), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('priority', sa.String(length=32), nullable=False, server_default='routine'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='draft'),
        sa.Column('author', sa.String(length=64), nullable=False, server_default=''),
        sa.Column('approved_by', sa.String(length=64), nullable=True),
        sa.Column('assigned_unit_ids', sa.JSON(), nullable=False),
        sa.Column('risk_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('estimated_duration_s', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('estimated_fuel_l', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    with op.batch_alter_table('missions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_missions_status'), ['status'], unique=False)

    # 2. mission_tasks
    op.create_table(
        'mission_tasks',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True, nullable=False),
        sa.Column('mission_id', sa.String(length=64), sa.ForeignKey('missions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('task_type', sa.String(length=32), nullable=False),
        sa.Column('target_entity', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('duration_s', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    with op.batch_alter_table('mission_tasks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_mission_tasks_mission_id'), ['mission_id'], unique=False)

    # 3. waypoints
    op.create_table(
        'waypoints',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True, nullable=False),
        sa.Column('mission_id', sa.String(length=64), sa.ForeignKey('missions.id', ondelete='CASCADE'), nullable=True),
        sa.Column('sequence', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lon', sa.Float(), nullable=False),
        sa.Column('alt_m', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('geom', app.models.SpatialPoint(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    with op.batch_alter_table('waypoints', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_waypoints_mission_id'), ['mission_id'], unique=False)

    # 4. routes
    op.create_table(
        'routes',
        sa.Column('id', sa.String(length=64), primary_key=True, nullable=False),
        sa.Column('mission_id', sa.String(length=64), sa.ForeignKey('missions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('unit_id', sa.String(length=64), nullable=False),
        sa.Column('strategy', sa.String(length=32), nullable=False, server_default='shortest'),
        sa.Column('distance_km', sa.Float(), nullable=False),
        sa.Column('estimated_duration_s', sa.Integer(), nullable=False),
        sa.Column('fuel_l', sa.Float(), nullable=False),
        sa.Column('risk_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('waypoints_json', sa.JSON(), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=False, server_default=''),
        sa.Column('geom', app.models.SpatialLineString(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    with op.batch_alter_table('routes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_routes_mission_id'), ['mission_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_routes_unit_id'), ['unit_id'], unique=False)

    # 5. route_segments
    op.create_table(
        'route_segments',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True, nullable=False),
        sa.Column('route_id', sa.String(length=64), sa.ForeignKey('routes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('segment_idx', sa.Integer(), nullable=False),
        sa.Column('start_lat', sa.Float(), nullable=False),
        sa.Column('start_lon', sa.Float(), nullable=False),
        sa.Column('end_lat', sa.Float(), nullable=False),
        sa.Column('end_lon', sa.Float(), nullable=False),
        sa.Column('distance_km', sa.Float(), nullable=False),
        sa.Column('terrain_cost', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('threat_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('weather_cost', sa.Float(), nullable=False, server_default='0.0'),
    )
    with op.batch_alter_table('route_segments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_route_segments_route_id'), ['route_id'], unique=False)

    # 6. warroom_presence
    op.create_table(
        'warroom_presence',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True, nullable=False),
        sa.Column('username', sa.String(length=64), unique=True, nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='online'),
        sa.Column('current_screen', sa.String(length=64), nullable=False, server_default='map'),
        sa.Column('cursor_lat', sa.Float(), nullable=True),
        sa.Column('cursor_lon', sa.Float(), nullable=True),
        sa.Column('last_heartbeat', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    with op.batch_alter_table('warroom_presence', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_warroom_presence_username'), ['username'], unique=True)

    # 7. warroom_tasks
    op.create_table(
        'warroom_tasks',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True, nullable=False),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('incident_id', sa.String(length=64), nullable=True),
        sa.Column('assigned_to', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='TODO'),
        sa.Column('priority', sa.String(length=32), nullable=False, server_default='MEDIUM'),
        sa.Column('created_by', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    with op.batch_alter_table('warroom_tasks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_warroom_tasks_assigned_to'), ['assigned_to'], unique=False)
        batch_op.create_index(batch_op.f('ix_warroom_tasks_incident_id'), ['incident_id'], unique=False)

    # 8. warroom_assignments
    op.create_table(
        'warroom_assignments',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True, nullable=False),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('warroom_tasks.id', ondelete='CASCADE'), nullable=True),
        sa.Column('incident_id', sa.String(length=64), nullable=True),
        sa.Column('from_user', sa.String(length=64), nullable=False),
        sa.Column('to_user', sa.String(length=64), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    with op.batch_alter_table('warroom_assignments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_warroom_assignments_incident_id'), ['incident_id'], unique=False)

    # 9. optimizer_runs
    op.create_table(
        'optimizer_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True, nullable=False),
        sa.Column('budget', sa.Float(), nullable=False),
        sa.Column('priorities_json', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='completed'),
        sa.Column('score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('recommendations_json', sa.JSON(), nullable=False),
        sa.Column('tradeoffs_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 10. redteam_scenarios
    op.create_table(
        'redteam_scenarios',
        sa.Column('id', sa.String(length=64), primary_key=True, nullable=False),
        sa.Column('mission_id', sa.String(length=64), nullable=True),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('risk_rating', sa.String(length=32), nullable=False, server_default='HIGH'),
        sa.Column('vulnerability_summary', sa.Text(), nullable=False, server_default=''),
        sa.Column('injects_json', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='staged'),
        sa.Column('approved_by', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    with op.batch_alter_table('redteam_scenarios', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_redteam_scenarios_mission_id'), ['mission_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('redteam_scenarios')
    op.drop_table('optimizer_runs')
    op.drop_table('warroom_assignments')
    op.drop_table('warroom_tasks')
    op.drop_table('warroom_presence')
    op.drop_table('route_segments')
    op.drop_table('routes')
    op.drop_table('waypoints')
    op.drop_table('mission_tasks')
    op.drop_table('missions')
