"""Fix wrong file_created_at

Revision ID: edb8a15d51b1
Revises: d10c55fbb7d2
Create Date: 2025-03-03 12:07:19.784356

"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import text
from urllib.parse import urlparse


# revision identifiers, used by Alembic.
revision: str = 'edb8a15d51b1'
down_revision: Union[str, None] = 'd10c55fbb7d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def get_db_type():
    config = op.get_context().config
    url = config.get_main_option("sqlalchemy.url")
    return urlparse(url).scheme

def upgrade() -> None:
    # First, get the number of records that need to be updated
    conn = op.get_bind()
    result = conn.execute(text("SELECT COUNT(*) FROM entities WHERE file_created_at > file_last_modified_at")).fetchone()
    
    affected_count = result[0] if result else 0
    print(f"Found {affected_count} records with file_created_at > file_last_modified_at")
    
    # Update all records where file_created_at > file_last_modified_at
    conn.execute(text("""
    UPDATE entities
    SET file_created_at = file_last_modified_at
    WHERE file_created_at > file_last_modified_at
    """))
    
    print(f"Fixed {affected_count} records with file_created_at > file_last_modified_at")


def downgrade() -> None:
    pass
