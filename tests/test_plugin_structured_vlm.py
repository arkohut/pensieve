import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest
import respx
from httpx import Response

from memos.plugins.structured_vlm.main import (
    parse_vlm_response_to_extracted,
    metadata_field_name,
    predict_structured,
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
