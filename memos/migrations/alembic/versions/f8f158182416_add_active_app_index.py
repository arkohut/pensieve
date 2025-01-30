"""add_active_app_index

Revision ID: f8f158182416
Revises: 04acdaf75664
Create Date: 2024-12-30 14:42:06.165967

"""
from typing import Sequence, Union
from urllib.parse import urlparse

from alembic import op
import sqlalchemy as sa
import sqlite_vec
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'f8f158182416'
down_revision: Union[str, None] = '04acdaf75664'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def get_db_type():
    config = op.get_context().config
    url = config.get_main_option("sqlalchemy.url")
    return urlparse(url).scheme


def upgrade() -> None:
    if get_db_type() != 'sqlite':
        return

    # 获取 bind 连接
    conn = op.get_bind()
    
    # 直接在连接上加载扩展
    conn.connection.enable_load_extension(True)
    sqlite_vec.load(conn.connection)
    
    # 检查索引是否存在
    inspector = inspect(conn)
    existing_indexes = inspector.get_indexes('metadata_entries')
    existing_index_names = [idx['name'] for idx in existing_indexes]
    
    # 如果索引不存在，才创建
    if 'idx_metadata_active_app' not in existing_index_names:
        conn.execute(
            sa.text('''
            CREATE INDEX idx_metadata_active_app 
            ON metadata_entries(key, entity_id, value) 
            WHERE key = 'active_app'
            ''')
        )


def downgrade() -> None:
    if get_db_type() != 'sqlite':
        return

    # 获取连接
    conn = op.get_bind()
    
    # 直接在连接上加载扩展
    conn.connection.enable_load_extension(True)
    sqlite_vec.load(conn.connection)
    
    # 检查索引是否存在
    inspector = inspect(conn)
    existing_indexes = inspector.get_indexes('metadata_entries')
    existing_index_names = [idx['name'] for idx in existing_indexes]
    
    # 如果索引存在，才删除
    if 'idx_metadata_active_app' in existing_index_names:
        conn.execute(sa.text('DROP INDEX idx_metadata_active_app'))
