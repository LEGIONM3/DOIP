"""phase3_digital_twin_schemas

Revision ID: 8b1f2930cd34
Revises: 7a0e8d19bc23
Create Date: 2026-10-01 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.models


# revision identifiers, used by Alembic.
revision: str = '8b1f2930cd34'
down_revision: Union[str, Sequence[str], None] = '7a0e8d19bc23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to include Phase 3 Digital Twin, Knowledge Graph, Vision, and Copilot tables."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. knowledge_graph_nodes
    if 'knowledge_graph_nodes' not in existing_tables:
        op.create_table(
            'knowledge_graph_nodes',
            sa.Column('id', sa.String(length=64), primary_key=True, nullable=False),
            sa.Column('entity_type', sa.String(length=32), nullable=False),
            sa.Column('label', sa.String(length=128), nullable=False),
            sa.Column('properties_json', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        )
        with op.batch_alter_table('knowledge_graph_nodes', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_knowledge_graph_nodes_entity_type'), ['entity_type'], unique=False)

    # 2. knowledge_graph_edges
    if 'knowledge_graph_edges' not in existing_tables:
        op.create_table(
            'knowledge_graph_edges',
            sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True, nullable=False),
            sa.Column('source_id', sa.String(length=64), nullable=False),
            sa.Column('target_id', sa.String(length=64), nullable=False),
            sa.Column('relation_type', sa.String(length=32), nullable=False),
            sa.Column('weight', sa.Float(), nullable=False, server_default='1.0'),
            sa.Column('properties_json', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        with op.batch_alter_table('knowledge_graph_edges', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_knowledge_graph_edges_source_id'), ['source_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_knowledge_graph_edges_target_id'), ['target_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_knowledge_graph_edges_relation_type'), ['relation_type'], unique=False)

    # 3. vision_detections
    if 'vision_detections' not in existing_tables:
        op.create_table(
            'vision_detections',
            sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True, nullable=False),
            sa.Column('frame_id', sa.String(length=64), nullable=False),
            sa.Column('tick', sa.Integer(), nullable=False),
            sa.Column('class_name', sa.String(length=32), nullable=False),
            sa.Column('confidence', sa.Float(), nullable=False),
            sa.Column('bbox_json', sa.JSON(), nullable=False),
            sa.Column('lat', sa.Float(), nullable=True),
            sa.Column('lon', sa.Float(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        with op.batch_alter_table('vision_detections', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_vision_detections_frame_id'), ['frame_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_vision_detections_tick'), ['tick'], unique=False)

    # 4. vision_tracks
    if 'vision_tracks' not in existing_tables:
        op.create_table(
            'vision_tracks',
            sa.Column('id', sa.String(length=64), primary_key=True, nullable=False),
            sa.Column('class_name', sa.String(length=32), nullable=False),
            sa.Column('first_tick', sa.Integer(), nullable=False),
            sa.Column('last_tick', sa.Integer(), nullable=False),
            sa.Column('trajectory_json', sa.JSON(), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    # 5. forecast_runs
    if 'forecast_runs' not in existing_tables:
        op.create_table(
            'forecast_runs',
            sa.Column('id', sa.String(length=64), primary_key=True, nullable=False),
            sa.Column('scenario_id', sa.String(length=64), nullable=False),
            sa.Column('tick', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('horizon_ticks', sa.Integer(), nullable=False, server_default='120'),
            sa.Column('predictions_json', sa.JSON(), nullable=False),
            sa.Column('confidence', sa.Float(), nullable=False, server_default='0.95'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        with op.batch_alter_table('forecast_runs', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_forecast_runs_scenario_id'), ['scenario_id'], unique=False)

    # 6. copilot_sessions
    if 'copilot_sessions' not in existing_tables:
        op.create_table(
            'copilot_sessions',
            sa.Column('id', sa.String(length=64), primary_key=True, nullable=False),
            sa.Column('mission_id', sa.String(length=64), nullable=True),
            sa.Column('title', sa.String(length=128), nullable=False),
            sa.Column('messages_json', sa.JSON(), nullable=False),
            sa.Column('proposals_json', sa.JSON(), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
            sa.Column('approved_by', sa.String(length=64), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    # 7. replay_reports
    if 'replay_reports' not in existing_tables:
        op.create_table(
            'replay_reports',
            sa.Column('id', sa.String(length=64), primary_key=True, nullable=False),
            sa.Column('run_id', sa.String(length=64), nullable=False),
            sa.Column('comparison_run_id', sa.String(length=64), nullable=True),
            sa.Column('summary', sa.Text(), nullable=False, server_default=''),
            sa.Column('turning_points_json', sa.JSON(), nullable=False),
            sa.Column('kpi_deltas_json', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        with op.batch_alter_table('replay_reports', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_replay_reports_run_id'), ['run_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema to drop Phase 3 tables."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    for table_name in [
        'replay_reports',
        'copilot_sessions',
        'forecast_runs',
        'vision_tracks',
        'vision_detections',
        'knowledge_graph_edges',
        'knowledge_graph_nodes',
    ]:
        if table_name in existing_tables:
            op.drop_table(table_name)
