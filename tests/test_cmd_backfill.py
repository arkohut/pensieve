import json
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

from memos.cmds.backfill import (
    list_unprocessed_entity_ids,
    process_one_entity,
    run_backfill,
)


@pytest.mark.asyncio
async def test_list_unprocessed_filters_already_processed():
    """Entities that already have the target metadata field are excluded."""
    # Two entities exist; entity 1 already has metadata, entity 2 does not.
    fake_conn = MagicMock()
    fake_cur = MagicMock()
    fake_cur.fetchall.return_value = [(2,)]  # SQL returns only entity 2
    fake_conn.cursor.return_value.__enter__.return_value = fake_cur
    with patch("memos.cmds.backfill._open_conn", return_value=fake_conn):
        ids = list(list_unprocessed_entity_ids(
            field="structured_vlm_v1_qwen3_6_35b",
            utc_start="20260321-160000", utc_end="20260420-160000",
        ))
    assert ids == [2]
    # Verify the SQL filtered correctly
    sql = fake_cur.execute.call_args[0][0]
    assert "metadata_entries" in sql.lower()
    assert "NOT EXISTS" in sql.upper() or "LEFT JOIN" in sql.upper()
    # Field name appears in the params, not the SQL text
    params = fake_cur.execute.call_args[0][1]
    assert "structured_vlm_v1_qwen3_6_35b" in params
    assert "20260321-160000" in params
    assert "20260420-160000" in params


@pytest.mark.asyncio
async def test_process_one_entity_calls_plugin_webhook():
    """process_one_entity POSTs the entity to the plugin webhook URL."""
    fake_client = AsyncMock()
    fake_client.post = AsyncMock(return_value=MagicMock(status_code=200))

    await process_one_entity(
        client=fake_client,
        plugin_url="http://localhost:8839/api/plugins/structured_vlm/",
        entity_url="http://localhost:8839/api/libraries/1/entities/42",
    )

    fake_client.post.assert_awaited_once()
    args, kwargs = fake_client.post.call_args
    # Plugin webhook receives the entity URL via Location header
    assert kwargs["headers"]["Location"].endswith("/entities/42")


@pytest.mark.asyncio
async def test_run_backfill_processes_each_entity_once():
    with patch("memos.cmds.backfill.list_unprocessed_entity_ids", return_value=[10, 11, 12]), \
         patch("memos.cmds.backfill.process_one_entity", new=AsyncMock()) as proc:
        await run_backfill(
            field="structured_vlm_v1_qwen3_6_35b",
            utc_start="20260321-160000", utc_end="20260420-160000",
            base_url="http://localhost:8839",
            library_id=1,
            concurrency=2,
        )
    assert proc.await_count == 3
