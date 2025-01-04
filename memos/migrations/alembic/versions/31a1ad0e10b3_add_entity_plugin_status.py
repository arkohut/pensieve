"""add_entity_plugin_status

Revision ID: 31a1ad0e10b3
Revises: 12504c5b1d3c
Create Date: 2025-01-03 13:47:44.291335

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31a1ad0e10b3'
down_revision: Union[str, None] = '12504c5b1d3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 entity_plugin_status 表
    op.create_table(
        'entity_plugin_status',
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('plugin_id', sa.Integer(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plugin_id'], ['plugins.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('entity_id', 'plugin_id'),
        if_not_exists=True
    )

    # 创建索引
    op.create_index('idx_entity_plugin_entity_id', 'entity_plugin_status', ['entity_id'], if_not_exists=True)
    op.create_index('idx_entity_plugin_plugin_id', 'entity_plugin_status', ['plugin_id'], if_not_exists=True)

    # 迁移现有数据
    # 注意：使用 execute() 执行原始 SQL
    op.execute("""
        INSERT INTO entity_plugin_status (entity_id, plugin_id, processed_at)
        SELECT DISTINCT 
            e.id as entity_id,
            p.id as plugin_id,
            e.last_scan_at as processed_at
        FROM entities e
        JOIN metadata_entries me ON e.id = me.entity_id
        JOIN plugins p ON p.name = 'builtin_ocr'
        WHERE me.source = 'ocr'
    """)

    op.execute("""
        INSERT INTO entity_plugin_status (entity_id, plugin_id, processed_at)
        SELECT DISTINCT 
            e.id as entity_id,
            p.id as plugin_id,
            e.last_scan_at as processed_at
        FROM entities e
        JOIN metadata_entries me ON e.id = me.entity_id
        JOIN plugins p ON p.name = 'builtin_vlm'
        WHERE me.source = 'vlm'
    """)


def downgrade() -> None:
    # 删除索引
    op.drop_index('idx_entity_plugin_plugin_id', table_name='entity_plugin_status')
    op.drop_index('idx_entity_plugin_entity_id', table_name='entity_plugin_status')
    
    # 删除表
    op.drop_table('entity_plugin_status')