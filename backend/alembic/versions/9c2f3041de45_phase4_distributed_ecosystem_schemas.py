"""phase4_distributed_ecosystem_schemas

Revision ID: 9c2f3041de45
Revises: 8b1f2930cd34
Create Date: 2026-10-01 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c2f3041de45'
down_revision: Union[str, Sequence[str], None] = '8b1f2930cd34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to include Phase 4 Distributed Autonomous Ecosystem tables."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. federation_nodes
    if 'federation_nodes' not in existing_tables:
        op.create_table(
            'federation_nodes',
            sa.Column('id', sa.String(64), primary_key=True),
            sa.Column('name', sa.String(128), nullable=False),
            sa.Column('tier', sa.String(32), nullable=False, default='tactical'),
            sa.Column('region', sa.String(64), nullable=False, default='GLOBAL'),
            sa.Column('endpoint', sa.String(256), nullable=False, default=''),
            sa.Column('status', sa.String(32), nullable=False, default='online'),
            sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('metadata_json', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_federation_nodes_tier', 'federation_nodes', ['tier'])
        op.create_index('ix_federation_nodes_region', 'federation_nodes', ['region'])

    # 2. theaters
    if 'theaters' not in existing_tables:
        op.create_table(
            'theaters',
            sa.Column('id', sa.String(64), primary_key=True),
            sa.Column('name', sa.String(128), nullable=False),
            sa.Column('code', sa.String(32), nullable=False, unique=True),
            sa.Column('bounds_json', sa.JSON(), nullable=False, server_default='[]'),
            sa.Column('active_world_id', sa.String(64), nullable=True),
            sa.Column('status', sa.String(32), nullable=False, default='active'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_theaters_code', 'theaters', ['code'])

    # 3. worlds
    if 'worlds' not in existing_tables:
        op.create_table(
            'worlds',
            sa.Column('id', sa.String(64), primary_key=True),
            sa.Column('theater_id', sa.String(64), nullable=False),
            sa.Column('name', sa.String(128), nullable=False),
            sa.Column('tick', sa.Integer(), nullable=False, default=0),
            sa.Column('status', sa.String(32), nullable=False, default='running'),
            sa.Column('state_snapshot_json', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_worlds_theater_id', 'worlds', ['theater_id'])

    # 4. campaigns
    if 'campaigns' not in existing_tables:
        op.create_table(
            'campaigns',
            sa.Column('id', sa.String(64), primary_key=True),
            sa.Column('title', sa.String(128), nullable=False),
            sa.Column('theater_ids_json', sa.JSON(), nullable=False, server_default='[]'),
            sa.Column('status', sa.String(32), nullable=False, default='draft'),
            sa.Column('objectives_json', sa.JSON(), nullable=False, server_default='[]'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )

    # 5. strategic_reports
    if 'strategic_reports' not in existing_tables:
        op.create_table(
            'strategic_reports',
            sa.Column('id', sa.String(64), primary_key=True),
            sa.Column('campaign_id', sa.String(64), nullable=True),
            sa.Column('title', sa.String(128), nullable=False),
            sa.Column('brief_text', sa.Text(), nullable=False, default=''),
            sa.Column('readiness_score', sa.Float(), nullable=False, default=85.0),
            sa.Column('risk_score', sa.Float(), nullable=False, default=25.0),
            sa.Column('outlook_json', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_strategic_reports_campaign_id', 'strategic_reports', ['campaign_id'])

    # 6. future_branches
    if 'future_branches' not in existing_tables:
        op.create_table(
            'future_branches',
            sa.Column('id', sa.String(64), primary_key=True),
            sa.Column('baseline_world_id', sa.String(64), nullable=False),
            sa.Column('branch_seed', sa.Integer(), nullable=False),
            sa.Column('ticks', sa.Integer(), nullable=False, default=120),
            sa.Column('outcome_rank', sa.Integer(), nullable=False, default=1),
            sa.Column('outcome_json', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('risk_band', sa.String(32), nullable=False, default='P50'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_future_branches_baseline_world_id', 'future_branches', ['baseline_world_id'])

    # 7. event_streams
    if 'event_streams' not in existing_tables:
        op.create_table(
            'event_streams',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('stream_name', sa.String(64), nullable=False),
            sa.Column('offset', sa.Integer(), nullable=False),
            sa.Column('partition', sa.Integer(), nullable=False, default=0),
            sa.Column('event_type', sa.String(64), nullable=False),
            sa.Column('payload_json', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_event_streams_stream_name', 'event_streams', ['stream_name'])
        op.create_index('ix_event_streams_offset', 'event_streams', ['offset'])

    # 8. data_lake_objects
    if 'data_lake_objects' not in existing_tables:
        op.create_table(
            'data_lake_objects',
            sa.Column('id', sa.String(64), primary_key=True),
            sa.Column('bucket', sa.String(64), nullable=False),
            sa.Column('key', sa.String(256), nullable=False),
            sa.Column('content_type', sa.String(64), nullable=False, default='application/json'),
            sa.Column('size_bytes', sa.Integer(), nullable=False, default=0),
            sa.Column('etag', sa.String(64), nullable=True),
            sa.Column('metadata_json', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_data_lake_objects_bucket', 'data_lake_objects', ['bucket'])
        op.create_index('ix_data_lake_objects_key', 'data_lake_objects', ['key'])


def downgrade() -> None:
    """Downgrade schema to remove Phase 4 tables."""
    for tbl in [
        'data_lake_objects',
        'event_streams',
        'future_branches',
        'strategic_reports',
        'campaigns',
        'worlds',
        'theaters',
        'federation_nodes',
    ]:
        op.drop_table(tbl)
