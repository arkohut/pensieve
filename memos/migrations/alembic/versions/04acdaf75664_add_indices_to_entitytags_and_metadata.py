"""Add indices to EntityTags and Metadata

Revision ID: 04acdaf75664
Revises: 00904ac8c6fc
Create Date: 2024-08-14 12:18:46.039436

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '04acdaf75664'
down_revision: Union[str, None] = '00904ac8c6fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 获取 inspector
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # 检查 entity_tags 表的索引
    entity_tags_indexes = inspector.get_indexes('entity_tags')
    entity_tags_index_names = [idx['name'] for idx in entity_tags_indexes]
    
    # 检查 metadata_entries 表的索引
    metadata_indexes = inspector.get_indexes('metadata_entries')
    metadata_index_names = [idx['name'] for idx in metadata_indexes]

    # 创建 entity_tags 的索引
    entity_tags_indices = [
        ('idx_entity_tag_entity_id', ['entity_id']),
        ('idx_entity_tag_tag_id', ['tag_id']),
    ]
    
    for idx_name, columns in entity_tags_indices:
        if idx_name not in entity_tags_index_names:
            op.create_index(idx_name, 'entity_tags', columns, unique=False)

    # 创建 metadata_entries 的索引
    metadata_indices = [
        ('idx_metadata_entity_id', ['entity_id']),
        ('idx_metadata_key', ['key']),
    ]
    
    for idx_name, columns in metadata_indices:
        if idx_name not in metadata_index_names:
            op.create_index(idx_name, 'metadata_entries', columns, unique=False)


def downgrade() -> None:
    # 获取 inspector
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # 检查现有索引
    entity_tags_indexes = inspector.get_indexes('entity_tags')
    entity_tags_index_names = [idx['name'] for idx in entity_tags_indexes]
    
    metadata_indexes = inspector.get_indexes('metadata_entries')
    metadata_index_names = [idx['name'] for idx in metadata_indexes]

    # 删除 metadata_entries 的索引
    metadata_indices = [
        'idx_metadata_key',
        'idx_metadata_entity_id',
    ]
    
    for idx_name in metadata_indices:
        if idx_name in metadata_index_names:
            op.drop_index(idx_name, table_name='metadata_entries')

    # 删除 entity_tags 的索引
    entity_tags_indices = [
        'idx_entity_tag_tag_id',
        'idx_entity_tag_entity_id',
    ]
    
    for idx_name in entity_tags_indices:
        if idx_name in entity_tags_index_names:
            op.drop_index(idx_name, table_name='entity_tags')
