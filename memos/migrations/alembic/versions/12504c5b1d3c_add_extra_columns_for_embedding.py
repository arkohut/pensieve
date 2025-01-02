"""add_extra_columns_for_embedding

Revision ID: 12504c5b1d3c
Revises: f8f158182416
Create Date: 2025-01-02 10:11:48.997145

"""
from typing import Sequence, Union

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


def upgrade() -> None:
    # First check if the table exists
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    print("Current tables:", tables)  # Debug info
    
    # Check if entities_vec_v2 exists and has data
    needs_data_copy = False
    if 'entities_vec_v2' in tables:
        # Check if the table is empty
        result = conn.execute(sa.text("SELECT COUNT(*) FROM entities_vec_v2")).scalar()
        print(f"Current row count in entities_vec_v2: {result}")  # Debug info
        if result == 0:
            needs_data_copy = True
            print("entities_vec_v2 exists but is empty, will copy data")  # Debug info
        else:
            print("entities_vec_v2 exists and has data, skipping migration")  # Debug info
            return
    
    try:
        # If table doesn't exist, create it
        if 'entities_vec_v2' not in tables:
            # 获取 bind 连接
            conn = op.get_bind()
            
            # 直接在连接上加载扩展
            print("Loading sqlite_vec extension...")  # Debug info
            conn.connection.enable_load_extension(True)
            sqlite_vec.load(conn.connection)
            print("sqlite_vec extension loaded successfully")  # Debug info

            # Create a temporary table with the new schema
            print("Creating entities_vec_v2 table...")  # Debug info
            conn.execute(
                sa.text(
                    f"""
                    CREATE VIRTUAL TABLE IF NOT EXISTS entities_vec_v2 USING vec0(
                        embedding float[{settings.embedding.num_dim}] distance_metric=cosine,
                        file_type_group text,
                        created_at_timestamp integer,
                        app_name text,
                        library_id integer
                    )
                    """
                )
            )
            print("Table entities_vec_v2 created successfully")  # Debug info
            needs_data_copy = True

        # Copy data if needed (either new table or empty existing table)
        if needs_data_copy and 'entities_vec' in tables:
            print("Starting data copy from entities_vec to entities_vec_v2...")  # Debug info
            result = conn.execute(
                sa.text("""
                    INSERT INTO entities_vec_v2(
                        embedding,
                        file_type_group,
                        created_at_timestamp,
                        app_name,
                        library_id
                    )
                    SELECT 
                        embedding,
                        'image',             -- default file_type_group
                        0,                   -- default created_at_timestamp
                        'unknown',           -- default app_name
                        1                    -- default library_id (assuming 1 is your default library)
                    FROM entities_vec
                """)
            )
            print(f"Data copy completed. Rows affected: {result.rowcount}")  # Debug info
        elif 'entities_vec' not in tables:
            print("Old table entities_vec not found, skipping data copy")  # Debug info

    except Exception as e:
        print(f"Error during migration: {str(e)}")  # Debug info
        raise  # Re-raise the exception after logging


def downgrade() -> None:
    pass
