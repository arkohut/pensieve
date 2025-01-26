"""add_extra_columns_for_embedding

Revision ID: 12504c5b1d3c
Revises: f8f158182416
Create Date: 2025-01-02 10:11:48.997145

"""
from typing import Sequence, Union
from urllib.parse import urlparse

from alembic import op
import sqlalchemy as sa
from memos.config import settings
import sqlite_vec
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '12504c5b1d3c'
down_revision: Union[str, None] = 'f8f158182416'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def get_db_type():
    config = op.get_context().config
    url = config.get_main_option("sqlalchemy.url")
    return urlparse(url).scheme


def upgrade() -> None:
    if get_db_type() != 'sqlite':
        return

    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    if 'entities_vec_v2' not in tables:
        conn = op.get_bind()
        
        print("Loading sqlite_vec extension...")
        conn.connection.enable_load_extension(True)
        sqlite_vec.load(conn.connection)
        print("sqlite_vec extension loaded successfully")

        print("Creating entities_vec_v2 table...")
        conn.execute(
            sa.text(
                f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS entities_vec_v2 USING vec0(
                    embedding float[{settings.embedding.num_dim}] distance_metric=cosine,
                    file_type_group text,
                    created_at_timestamp integer,
                    file_created_at_timestamp integer,
                    file_created_at_date text partition key,
                    app_name text,
                    library_id integer
                )
                """
            )
        )
        print("Table entities_vec_v2 created successfully")


def downgrade() -> None:
    pass
