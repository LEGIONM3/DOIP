"""phase5_unified_platform_schemas

Revision ID: a1c3e5f7a9b0
Revises: 9c2f3041de45
Create Date: 2026-10-03 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c3e5f7a9b0'
down_revision: Union[str, Sequence[str], None] = '9c2f3041de45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to include Phase 5 Unified Enterprise Platform tables."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. agents
    if 'agents' not in existing_tables:
        op.create_table(
            'agents',
            sa.Column('id', sa.String(64), primary_key=True),
            sa.Column('name', sa.String(128), nullable=False),
            sa.Column('role', sa.String(64), nullable=False),
            sa.Column('status', sa.String(32), nullable=False, default='idle'),
            sa.Column('capabilities_json', sa.JSON(), nullable=False, server_default='[]'),
            sa.Column('metadata_json', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_agents_role', 'agents', ['role'])

    # 2. agent_tasks
    if 'agent_tasks' not in existing_tables:
        op.create_table(
            'agent_tasks',
            sa.Column('id', sa.String(64), primary_key=True),
            sa.Column('agent_id', sa.String(64), nullable=True),
            sa.Column('task_type', sa.String(64), nullable=False),
            sa.Column('payload_json', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('result_json', sa.JSON(), nullable=True),
            sa.Column('status', sa.String(32), nullable=False, default='pending'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('ix_agent_tasks_agent_id', 'agent_tasks', ['agent_id'])
        op.create_index('ix_agent_tasks_task_type', 'agent_tasks', ['task_type'])

    # 3. agent_memories
    if 'agent_memories' not in existing_tables:
        op.create_table(
            'agent_memories',
            sa.Column('id', sa.String(64), primary_key=True),
            sa.Column('agent_id', sa.String(64), nullable=True),
            sa.Column('memory_type', sa.String(32), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('tags_json', sa.JSON(), nullable=False, server_default='[]'),
            sa.Column('embedding_json', sa.JSON(), nullable=True),
            sa.Column('importance', sa.Float(), nullable=False, default=1.0),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_agent_memories_agent_id', 'agent_memories', ['agent_id'])
        op.create_index('ix_agent_memories_memory_type', 'agent_memories', ['memory_type'])

    # 4. analysis_findings
    if 'analysis_findings' not in existing_tables:
        op.create_table(
            'analysis_findings',
            sa.Column('id', sa.String(64), primary_key=True),
            sa.Column('category', sa.String(32), nullable=False),
            sa.Column('severity', sa.String(32), nullable=False, default='medium'),
            sa.Column('title', sa.String(256), nullable=False),
            sa.Column('details_json', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_analysis_findings_category', 'analysis_findings', ['category'])

    # 5. forecast_matrices
    if 'forecast_matrices' not in existing_tables:
        op.create_table(
            'forecast_matrices',
            sa.Column('id', sa.String(64), primary_key=True),
            sa.Column('horizon_hours', sa.Float(), nullable=False, default=4.0),
            sa.Column('matrix_json', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('risk_tensor_json', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('summary', sa.Text(), nullable=False, default=''),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # 6. scenario_outcomes
    if 'scenario_outcomes' not in existing_tables:
        op.create_table(
            'scenario_outcomes',
            sa.Column('id', sa.String(64), primary_key=True),
            sa.Column('batch_id', sa.String(64), nullable=False),
            sa.Column('scenario_seed', sa.Integer(), nullable=False),
            sa.Column('score', sa.Float(), nullable=False, default=0.0),
            sa.Column('rank', sa.Integer(), nullable=False, default=1),
            sa.Column('outcome_json', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_scenario_outcomes_batch_id', 'scenario_outcomes', ['batch_id'])

    # 7. model_registry
    if 'model_registry' not in existing_tables:
        op.create_table(
            'model_registry',
            sa.Column('id', sa.String(64), primary_key=True),
            sa.Column('name', sa.String(128), nullable=False),
            sa.Column('provider', sa.String(64), nullable=False),
            sa.Column('model_type', sa.String(32), nullable=False),
            sa.Column('endpoint', sa.String(256), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
            sa.Column('metadata_json', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # 8. workflow_instances
    if 'workflow_instances' not in existing_tables:
        op.create_table(
            'workflow_instances',
            sa.Column('id', sa.String(64), primary_key=True),
            sa.Column('workflow_type', sa.String(64), nullable=False),
            sa.Column('title', sa.String(256), nullable=False),
            sa.Column('current_step', sa.String(64), nullable=False),
            sa.Column('steps_json', sa.JSON(), nullable=False, server_default='[]'),
            sa.Column('status', sa.String(32), nullable=False, default='staged'),
            sa.Column('requires_human_confirmation', sa.Boolean(), nullable=False, default=True),
            sa.Column('approved_by', sa.String(64), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_workflow_instances_workflow_type', 'workflow_instances', ['workflow_type'])

    # 9. operational_reports
    if 'operational_reports' not in existing_tables:
        op.create_table(
            'operational_reports',
            sa.Column('id', sa.String(64), primary_key=True),
            sa.Column('report_type', sa.String(64), nullable=False),
            sa.Column('title', sa.String(256), nullable=False),
            sa.Column('content_md', sa.Text(), nullable=False, default=''),
            sa.Column('data_json', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_operational_reports_report_type', 'operational_reports', ['report_type'])


def downgrade() -> None:
    """Downgrade schema removing Phase 5 tables."""
    for table_name in [
        'operational_reports',
        'workflow_instances',
        'model_registry',
        'scenario_outcomes',
        'forecast_matrices',
        'analysis_findings',
        'agent_memories',
        'agent_tasks',
        'agents',
    ]:
        op.drop_table(table_name)
