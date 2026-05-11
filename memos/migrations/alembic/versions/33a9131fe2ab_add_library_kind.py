"""add library kind

Revision ID: 33a9131fe2ab
Revises: fa40c9f33551
Create Date: 2026-05-11 12:23:15.119981

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from urllib.parse import urlparse


# revision identifiers, used by Alembic.
revision: str = '33a9131fe2ab'
down_revision: Union[str, None] = 'fa40c9f33551'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def get_db_type():
    config = op.get_context().config
    url = config.get_main_option("sqlalchemy.url")
    return urlparse(url).scheme

def upgrade() -> None:
    # Libraries: introduce a kind discriminator so we can branch UI / API
    # behavior between continuous-capture record streams and static
    # collections.
    op.add_column(
        "libraries",
        sa.Column(
            "kind",
            sa.String(length=16),
            nullable=False,
            server_default="static",
        ),
    )

    # Backfill: the configured default library (continuous screen capture)
    # gets kind=record. All other libraries stay static; users can manually
    # promote them via the PATCH endpoint.
    from memos.config import settings

    op.execute(
        sa.text("UPDATE libraries SET kind = 'record' WHERE name = :name").bindparams(
            name=settings.default_library
        )
    )


def downgrade() -> None:
    op.drop_column("libraries", "kind")
