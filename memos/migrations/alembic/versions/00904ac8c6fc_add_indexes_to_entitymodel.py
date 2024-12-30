"""Add indexes to EntityModel

Revision ID: 00904ac8c6fc
Revises: 
Create Date: 2024-07-17 12:16:59.911285

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '00904ac8c6fc'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 获取 inspector
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_indexes = inspector.get_indexes('entities')
    existing_index_names = [idx['name'] for idx in existing_indexes]

    # 要创建的索引列表
    indexes = [
        ('idx_file_type', ['file_type']),
        ('idx_filename', ['filename']),
        ('idx_filepath', ['filepath']),
        ('idx_folder_id', ['folder_id']),
        ('idx_library_id', ['library_id']),
    ]

    # 只创建不存在的索引
    for idx_name, columns in indexes:
        if idx_name not in existing_index_names:
            op.create_index(idx_name, 'entities', columns, unique=False)


def downgrade() -> None:
    # 获取 inspector
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_indexes = inspector.get_indexes('entities')
    existing_index_names = [idx['name'] for idx in existing_indexes]

    # 要删除的索引列表
    indexes = [
        'idx_library_id',
        'idx_folder_id',
        'idx_filepath',
        'idx_filename',
        'idx_file_type',
    ]

    # 只删除存在的索引
    for idx_name in indexes:
        if idx_name in existing_index_names:
            op.drop_index(idx_name, table_name='entities')
