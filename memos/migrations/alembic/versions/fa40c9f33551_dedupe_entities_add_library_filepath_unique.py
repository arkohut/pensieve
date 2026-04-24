"""dedupe entities and add unique (library_id, filepath)

Revision ID: fa40c9f33551
Revises: edb8a15d51b1
Create Date: 2026-04-24 10:30:00.000000

Removes duplicate rows in `entities` that share (library_id, filepath) — historical
residue from before commit 018c8c2 scoped get_entity_by_filepath to library_id.
For each duplicate group, keeps the row with the largest id (most recent write)
and drops the rest plus their rows in metadata_entries, entities_fts, and
entities_vec_v2. entity_plugin_status and entity_tags are removed automatically
via ON DELETE CASCADE.

Then adds a UNIQUE (library_id, filepath) constraint so this can't recur.

Idempotent: if no duplicates remain and the constraint already exists, both
steps are no-ops.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "fa40c9f33551"
down_revision: Union[str, None] = "edb8a15d51b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CONSTRAINT_NAME = "entities_library_filepath_unique"


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            CREATE TEMPORARY TABLE _dedup_victims AS
            SELECT id FROM (
                SELECT id,
                       MAX(id) OVER (PARTITION BY library_id, filepath) AS keep_id
                FROM entities
                WHERE (library_id, filepath) IN (
                    SELECT library_id, filepath FROM entities
                    GROUP BY library_id, filepath HAVING COUNT(*) > 1
                )
            ) t
            WHERE id <> keep_id
            """
        )
    )

    conn.execute(sa.text("DELETE FROM metadata_entries WHERE entity_id IN (SELECT id FROM _dedup_victims)"))
    conn.execute(sa.text("DELETE FROM entities_fts     WHERE id        IN (SELECT id FROM _dedup_victims)"))
    conn.execute(sa.text("DELETE FROM entities_vec_v2  WHERE rowid     IN (SELECT id FROM _dedup_victims)"))
    conn.execute(sa.text("DELETE FROM entities         WHERE id        IN (SELECT id FROM _dedup_victims)"))
    conn.execute(sa.text("DROP TABLE _dedup_victims"))

    existing = {uc["name"] for uc in sa.inspect(conn).get_unique_constraints("entities")}
    if CONSTRAINT_NAME not in existing:
        op.create_unique_constraint(CONSTRAINT_NAME, "entities", ["library_id", "filepath"])


def downgrade() -> None:
    existing = {uc["name"] for uc in sa.inspect(op.get_bind()).get_unique_constraints("entities")}
    if CONSTRAINT_NAME in existing:
        op.drop_constraint(CONSTRAINT_NAME, "entities", type_="unique")
