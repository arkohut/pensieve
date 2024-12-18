"""Add indices to EntityTags and Metadata

Revision ID: 04acdaf75664
Revises: 00904ac8c6fc
Create Date: 2024-08-14 12:18:46.039436

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '04acdaf75664'
down_revision: Union[str, None] = '00904ac8c6fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index('idx_entity_tag_entity_id', 'entity_tags', ['entity_id'], unique=False)
    op.create_index('idx_entity_tag_tag_id', 'entity_tags', ['tag_id'], unique=False)
    op.create_index('idx_metadata_entity_id', 'metadata_entries', ['entity_id'], unique=False)
    op.create_index('idx_metadata_key', 'metadata_entries', ['key'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('idx_metadata_key', table_name='metadata_entries')
    op.drop_index('idx_metadata_entity_id', table_name='metadata_entries')
    op.drop_index('idx_entity_tag_tag_id', table_name='entity_tags')
    op.drop_index('idx_entity_tag_entity_id', table_name='entity_tags')
    # ### end Alembic commands ###
