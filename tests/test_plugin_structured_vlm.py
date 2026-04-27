import json
from pathlib import Path

import httpx
import pytest
import respx
from httpx import Response

from memos.plugins.structured_vlm.main import (
    parse_vlm_response_to_extracted,
    metadata_field_name,
    predict_structured,
    FAIL_HTTP_4XX,
    FAIL_HTTP_5XX,
    FAIL_NETWORK,
    FAIL_SCHEMA,
    FAIL_JSON_PARSE,
)
from memos.extractors.schema import ExtractedFields

FIXTURES = Path(__file__).parent / "fixtures"


def test_metadata_field_name_uses_versioned_id():
    name = metadata_field_name(modelname="qwen3.6-35b")
    assert name == "structured_vlm_v1_qwen3_6_35b"


def test_parse_clean_json_response():
    raw = (FIXTURES / "vlm_responses" / "iterm_cc_task.json").read_text()
    result = parse_vlm_response_to_extracted(raw, modelname="qwen3.6-35b")
    assert isinstance(result, ExtractedFields)
    assert result.extractor == "structured_vlm_v1_qwen3_6_35b"
    assert result.primary.workspace == "openbayes-gear-controller"
    assert result.primary.app == "iTerm2"


def test_parse_strips_markdown_codeblock():
    """If model wraps JSON in ```json ... ```, parser still succeeds."""
    raw = '```json\n{"primary": {"app": "Cursor"}, "confidence": {}}\n```'
    result = parse_vlm_response_to_extracted(raw, modelname="qwen3.6-35b")
    assert result.primary.app == "Cursor"


def test_parse_returns_none_on_unrecoverable_garbage():
    raw = "this is not json at all and contains no recoverable braces"
    result = parse_vlm_response_to_extracted(raw, modelname="qwen3.6-35b")
    assert result is None


@pytest.mark.asyncio
async def test_predict_structured_calls_vlm_and_parses(tmp_path):
    """The full predict_structured path mocks the VLM call and returns a parsed ExtractedFields."""
    img_path = FIXTURES / "screenshots" / "sample_iterm_cc.webp"
    canned_response_text = (FIXTURES / "vlm_responses" / "iterm_cc_task.json").read_text()
    api_envelope = {
        "choices": [{"message": {"content": canned_response_text}}]
    }

    with respx.mock(base_url="https://fake-vlm.test") as mock:
        mock.post("/v1/chat/completions").mock(return_value=Response(200, json=api_envelope))
        result = await predict_structured(
            endpoint="https://fake-vlm.test",
            modelname="qwen3.6-35b",
            img_path=str(img_path),
            token=None,
        )

    assert result is not None
    assert result.primary.workspace == "openbayes-gear-controller"


# --- Retry / failure-category coverage ---


@pytest.fixture
def img_path():
    return str(FIXTURES / "screenshots" / "sample_iterm_cc.webp")


@pytest.fixture
def good_envelope():
    canned = (FIXTURES / "vlm_responses" / "iterm_cc_task.json").read_text()
    return {"choices": [{"message": {"content": canned}}]}


@pytest.mark.asyncio
async def test_predict_retries_on_5xx_then_succeeds(img_path, good_envelope):
    """Two 503s then a 200 should yield a successful parse."""
    with respx.mock(base_url="https://fake-vlm.test") as mock:
        mock.post("/v1/chat/completions").mock(side_effect=[
            Response(503, text="upstream busy"),
            Response(503, text="upstream busy"),
            Response(200, json=good_envelope),
        ])
        result = await predict_structured(
            endpoint="https://fake-vlm.test",
            modelname="qwen3.6-35b",
            img_path=img_path,
            token=None,
            retry_base_delay=0,  # zero backoff for fast tests
        )
    assert result is not None
    assert result.primary.workspace == "openbayes-gear-controller"


@pytest.mark.asyncio
async def test_predict_gives_up_after_max_retries_on_5xx(img_path, caplog):
    """All 5xx → None, with category=http_5xx logged."""
    caplog.set_level("WARNING", logger="memos.plugins.structured_vlm.main")
    with respx.mock(base_url="https://fake-vlm.test") as mock:
        mock.post("/v1/chat/completions").mock(return_value=Response(503, text="busy"))
        result = await predict_structured(
            endpoint="https://fake-vlm.test",
            modelname="qwen3.6-35b",
            img_path=img_path,
            token=None,
            max_retries=3,
            retry_base_delay=0,
            entity_id=999,
        )
    assert result is None
    assert any(
        f"category={FAIL_HTTP_5XX}" in r.message and "entity_id=999" in r.message
        for r in caplog.records
    )


@pytest.mark.asyncio
async def test_predict_does_not_retry_on_4xx(img_path, caplog):
    """4xx is terminal — single call, category=http_4xx."""
    caplog.set_level("WARNING", logger="memos.plugins.structured_vlm.main")
    with respx.mock(base_url="https://fake-vlm.test") as mock:
        route = mock.post("/v1/chat/completions").mock(return_value=Response(400, text="bad payload"))
        result = await predict_structured(
            endpoint="https://fake-vlm.test",
            modelname="qwen3.6-35b",
            img_path=img_path,
            token=None,
            max_retries=3,
            retry_base_delay=0,
        )
    assert result is None
    assert route.call_count == 1
    assert any(f"category={FAIL_HTTP_4XX}" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_predict_retries_on_network_error(img_path, good_envelope):
    """Connection error first, then success."""
    with respx.mock(base_url="https://fake-vlm.test") as mock:
        mock.post("/v1/chat/completions").mock(side_effect=[
            httpx.ConnectError("conn reset"),
            Response(200, json=good_envelope),
        ])
        result = await predict_structured(
            endpoint="https://fake-vlm.test",
            modelname="qwen3.6-35b",
            img_path=img_path,
            token=None,
            retry_base_delay=0,
        )
    assert result is not None


@pytest.mark.asyncio
async def test_predict_logs_schema_failure_category(img_path, caplog):
    """Model emits valid JSON that violates the schema → category=schema_validation."""
    caplog.set_level("WARNING", logger="memos.plugins.structured_vlm.main")
    bad_envelope = {
        "choices": [{"message": {"content": json.dumps({"primary": {"app": 12345}})}}]
    }
    with respx.mock(base_url="https://fake-vlm.test") as mock:
        mock.post("/v1/chat/completions").mock(return_value=Response(200, json=bad_envelope))
        result = await predict_structured(
            endpoint="https://fake-vlm.test",
            modelname="qwen3.6-35b",
            img_path=img_path,
            token=None,
            retry_base_delay=0,
            entity_id=42,
        )
    assert result is None
    assert any(
        f"category={FAIL_SCHEMA}" in r.message and "entity_id=42" in r.message
        for r in caplog.records
    )


@pytest.mark.asyncio
async def test_predict_logs_json_parse_failure_category(img_path, caplog):
    """Model returns garbage that has no JSON → category=json_parse."""
    caplog.set_level("WARNING", logger="memos.plugins.structured_vlm.main")
    bad_envelope = {"choices": [{"message": {"content": "this is not json"}}]}
    with respx.mock(base_url="https://fake-vlm.test") as mock:
        mock.post("/v1/chat/completions").mock(return_value=Response(200, json=bad_envelope))
        result = await predict_structured(
            endpoint="https://fake-vlm.test",
            modelname="qwen3.6-35b",
            img_path=img_path,
            token=None,
            retry_base_delay=0,
        )
    assert result is None
    assert any(f"category={FAIL_JSON_PARSE}" in r.message for r in caplog.records)
