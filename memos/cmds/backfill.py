"""Backfill CLI commands. Currently: structured_vlm extractor.

Usage:
  memos backfill structured-vlm --days 30 --concurrency 8
"""
from __future__ import annotations
import asyncio
import logging
from typing import Iterator, Optional

import httpx
import typer

from memos.config import settings
from memos.tz_utils import LocalOffset, local_date_to_utc_range
from memos.plugins.structured_vlm.main import metadata_field_name as svlm_field_name

logger = logging.getLogger(__name__)

backfill_app = typer.Typer(help="Backfill commands for derived metadata.")


def _open_conn():
    """Open a psycopg2 connection from the configured database URL.

    psycopg2 accepts full DSN/URL strings natively, so no manual parsing needed.
    Lazy-imported so tests without psycopg2 still load the module.
    """
    import psycopg2
    url = settings.database_url
    # psycopg2 accepts postgres:// and postgresql://; normalize the SQLAlchemy variant
    if url.startswith("postgresql://"):
        url = "postgres://" + url[len("postgresql://"):]
    return psycopg2.connect(url)


def list_unprocessed_entity_ids(field: str, utc_start: str, utc_end: str) -> Iterator[int]:
    """Yield entity IDs in [utc_start, utc_end) that do NOT yet have the given metadata field."""
    conn = _open_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.id FROM entities e
                JOIN metadata_entries m_ts ON m_ts.entity_id = e.id AND m_ts.key = 'timestamp'
                WHERE m_ts.value >= %s AND m_ts.value < %s
                  AND NOT EXISTS (
                    SELECT 1 FROM metadata_entries m
                    WHERE m.entity_id = e.id AND m.key = %s
                  )
                ORDER BY m_ts.value;
                """,
                (utc_start, utc_end, field),
            )
            for (eid,) in cur.fetchall():
                yield eid
    finally:
        conn.close()


async def process_one_entity(client, plugin_url: str, entity_url: str) -> None:
    """POST to the plugin webhook with Location header pointing at the entity."""
    try:
        r = await client.post(
            plugin_url,
            headers={"Location": entity_url},
            json={},  # plugin loads entity via location
            timeout=300.0,
        )
        if r.status_code != 200:
            logger.warning(f"Plugin returned {r.status_code} for {entity_url}: {r.text[:200]}")
    except Exception as e:
        logger.warning(f"Backfill failed for {entity_url}: {e}")


async def run_backfill(field: str, utc_start: str, utc_end: str,
                       base_url: str, library_id: int, concurrency: int) -> None:
    plugin_url = f"{base_url}/api/plugins/structured_vlm/"
    ids = list(list_unprocessed_entity_ids(field=field, utc_start=utc_start, utc_end=utc_end))
    total = len(ids)
    print(f"To process: {total} entities. Concurrency: {concurrency}.")
    if total == 0:
        return
    sem = asyncio.Semaphore(concurrency)
    done = 0

    async def one(client, eid: int):
        nonlocal done
        entity_url = f"{base_url}/api/libraries/{library_id}/entities/{eid}"
        async with sem:
            await process_one_entity(client, plugin_url, entity_url)
            done += 1
            if done % 50 == 0 or done == total:
                print(f"  [{done}/{total}] processed")

    async with httpx.AsyncClient() as client:
        await asyncio.gather(*(one(client, eid) for eid in ids))
    print(f"Done: {done}/{total} processed.")


@backfill_app.command("structured-vlm")
def cmd_structured_vlm(
    days: int = typer.Option(30, "--days", help="How many days back from today (local) to backfill."),
    concurrency: int = typer.Option(4, "--concurrency", help="Concurrent webhook requests."),
    library_id: int = typer.Option(1, "--lib", help="Library ID for entity URL composition."),
    base_url: Optional[str] = typer.Option(
        None, "--base-url",
        help="Server base URL (defaults to settings.server_endpoint).",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print count of unprocessed and exit."),
):
    """Run structured_vlm extraction on screenshots from the last N local days."""
    from datetime import datetime, timedelta
    offset = LocalOffset.from_system()
    modelname = settings.structured_vlm.modelname
    if not modelname:
        raise typer.BadParameter(
            "structured_vlm.modelname is not configured. Set it in ~/.memos/config.yaml "
            "(e.g., modelname: qwen3.6-35b)."
        )
    today_local = datetime.now()
    end_local = today_local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    start_local = end_local - timedelta(days=days)
    utc_start, _ = local_date_to_utc_range(start_local.strftime("%Y%m%d"), offset)
    _, utc_end = local_date_to_utc_range((end_local - timedelta(days=1)).strftime("%Y%m%d"), offset)

    field = svlm_field_name(modelname=modelname)
    base = base_url or settings.server_endpoint

    print(f"Backfill: field={field}, UTC range [{utc_start}, {utc_end}), base_url={base}")
    if dry_run:
        ids = list(list_unprocessed_entity_ids(field=field, utc_start=utc_start, utc_end=utc_end))
        print(f"DRY RUN: {len(ids)} entities would be processed.")
        return

    asyncio.run(run_backfill(
        field=field, utc_start=utc_start, utc_end=utc_end,
        base_url=base, library_id=library_id, concurrency=concurrency,
    ))
