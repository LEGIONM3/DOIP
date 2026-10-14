"""phase1_initial_schema

Revision ID: 60bd2854aa56
Revises: 
Create Date: 2026-10-01 13:12:54.091657

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.models


# revision identifiers, used by Alembic.
revision: str = '60bd2854aa56'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.create_table('audit_events',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('actor', sa.String(length=64), nullable=False),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('detail', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_events_action'), ['action'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_events_actor'), ['actor'], unique=False)

    op.create_table('custom_scenarios',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('scenario_id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('config_json', sa.Text(), nullable=False),
    sa.Column('actions_json', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('author', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('custom_scenarios', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_custom_scenarios_scenario_id'), ['scenario_id'], unique=True)

    op.create_table('doctrine_documents',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('doc_id', sa.String(length=32), nullable=False),
    sa.Column('category', sa.String(length=32), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('tags', sa.JSON(), nullable=False),
    sa.Column('version', sa.String(length=16), nullable=False),
    sa.Column('source_file', sa.String(length=255), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('doctrine_documents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_doctrine_documents_category'), ['category'], unique=False)
        batch_op.create_index(batch_op.f('ix_doctrine_documents_doc_id'), ['doc_id'], unique=True)

    op.create_table('runs',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('seed', sa.BigInteger(), nullable=False),
    sa.Column('scenario_id', sa.String(length=64), nullable=False),
    sa.Column('ticks', sa.Integer(), nullable=False),
    sa.Column('events_count', sa.Integer(), nullable=False),
    sa.Column('log', sa.Text(), nullable=False),
    sa.Column('world_json', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('runs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_runs_scenario_id'), ['scenario_id'], unique=False)

    op.create_table('tactical_zones',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('zone_id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('zone_type', sa.String(length=32), nullable=False),
    sa.Column('min_alt_m', sa.Float(), nullable=False),
    sa.Column('max_alt_m', sa.Float(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('coordinates_json', sa.JSON(), nullable=False),
    sa.Column('geom', app.models.SpatialPolygon(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('tactical_zones', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tactical_zones_zone_id'), ['zone_id'], unique=True)

    op.create_table('users',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('username', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=True),
    sa.Column('role', sa.String(length=32), nullable=False),
    sa.Column('unit', sa.String(length=64), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_username'), ['username'], unique=True)

    op.create_table('warroom_messages',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('type', sa.String(length=32), nullable=False),
    sa.Column('payload', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('whatif_results',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('seed', sa.BigInteger(), nullable=False),
    sa.Column('scenario_id', sa.String(length=64), nullable=False),
    sa.Column('ticks', sa.Integer(), nullable=False),
    sa.Column('actions_json', sa.Text(), nullable=False),
    sa.Column('baseline_kpis', sa.Text(), nullable=False),
    sa.Column('branch_kpis', sa.Text(), nullable=False),
    sa.Column('deltas_json', sa.Text(), nullable=False),
    sa.Column('score', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('whatif_results', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_whatif_results_scenario_id'), ['scenario_id'], unique=False)

    op.create_table('doctrine_chunks',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('chunk_id', sa.String(length=64), nullable=False),
    sa.Column('document_id', sa.String(length=32), nullable=False),
    sa.Column('document_type', sa.String(length=16), nullable=False),
    sa.Column('section', sa.String(length=128), nullable=False),
    sa.Column('source', sa.String(length=255), nullable=False),
    sa.Column('citation', sa.String(length=64), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('token_count', sa.Integer(), nullable=False),
    sa.Column('embedding', app.models.VectorType(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['doctrine_documents.doc_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('doctrine_chunks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_doctrine_chunks_chunk_id'), ['chunk_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_doctrine_chunks_document_id'), ['document_id'], unique=False)

    op.create_table('sim_events',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('run_id', sa.String(length=64), nullable=False),
    sa.Column('tick', sa.Integer(), nullable=False),
    sa.Column('event_type', sa.String(length=64), nullable=False),
    sa.Column('severity', sa.String(length=16), nullable=False),
    sa.Column('entity_id', sa.String(length=64), nullable=False),
    sa.Column('lat', sa.Float(), nullable=True),
    sa.Column('lon', sa.Float(), nullable=True),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('geom', app.models.SpatialPoint(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('sim_events', schema=None) as batch_op:
        batch_op.create_index('idx_sim_events_run_tick', ['run_id', 'tick'], unique=False)
        batch_op.create_index('idx_sim_events_type_sev', ['event_type', 'severity'], unique=False)
        batch_op.create_index(batch_op.f('ix_sim_events_entity_id'), ['entity_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_sim_events_event_type'), ['event_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_sim_events_run_id'), ['run_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_sim_events_tick'), ['tick'], unique=False)

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('sim_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sim_events_tick'))
        batch_op.drop_index(batch_op.f('ix_sim_events_run_id'))
        batch_op.drop_index(batch_op.f('ix_sim_events_event_type'))
        batch_op.drop_index(batch_op.f('ix_sim_events_entity_id'))
        batch_op.drop_index('idx_sim_events_type_sev')
        batch_op.drop_index('idx_sim_events_run_tick')

    op.drop_table('sim_events')
    with op.batch_alter_table('doctrine_chunks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_doctrine_chunks_document_id'))
        batch_op.drop_index(batch_op.f('ix_doctrine_chunks_chunk_id'))

    op.drop_table('doctrine_chunks')
    with op.batch_alter_table('whatif_results', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_whatif_results_scenario_id'))

    op.drop_table('whatif_results')
    op.drop_table('warroom_messages')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_username'))

    op.drop_table('users')
    with op.batch_alter_table('tactical_zones', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tactical_zones_zone_id'))

    op.drop_table('tactical_zones')
    with op.batch_alter_table('runs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_runs_scenario_id'))

    op.drop_table('runs')
    with op.batch_alter_table('doctrine_documents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_doctrine_documents_doc_id'))
        batch_op.drop_index(batch_op.f('ix_doctrine_documents_category'))

    op.drop_table('doctrine_documents')
    with op.batch_alter_table('custom_scenarios', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_custom_scenarios_scenario_id'))

    op.drop_table('custom_scenarios')
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_events_actor'))
        batch_op.drop_index(batch_op.f('ix_audit_events_action'))

    op.drop_table('audit_events')
    # ### end Alembic commands ###
