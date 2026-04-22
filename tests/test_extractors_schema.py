import json
import pytest
from pydantic import ValidationError

from memos.extractors.schema import (
    ExtractedFields, PrimaryRegion, SecondaryRegion, Confidence
)


def test_minimal_valid_extraction():
    """The minimum required: extractor id + a primary.app."""
    e = ExtractedFields(
        extractor="title_regex_v1",
        primary=PrimaryRegion(app="iTerm2"),
    )
    assert e.extractor == "title_regex_v1"
    assert e.primary.app == "iTerm2"
    assert e.primary.tool is None
    assert e.primary.workspace is None
    assert e.secondary == []
    assert e.contact is None
    assert e.url is None
    assert e.notes is None


def test_full_extraction_round_trip():
    """A fully populated extraction serializes to JSON and back unchanged."""
    e = ExtractedFields(
        extractor="structured_vlm_v1_qwen36_35b",
        primary=PrimaryRegion(
            app="iTerm2",
            tool="Claude Code",
            what="Debug gear controller blocking issue with bayesjob",
            title_or_topic="Debug gear controller blocking issue with bayesjob",
            workspace="openbayes-gear-controller",
        ),
        secondary=[SecondaryRegion(app="iTerm2", what="git diff in adjacent pane")],
        contact=None,
        url="http://localhost:5174/",
        confidence=Confidence(primary="high", contact=None, url="high"),
        notes="iTerm2 split-pane: top pane Claude Code, bottom pane shell",
    )
    j = e.model_dump_json()
    e2 = ExtractedFields.model_validate_json(j)
    assert e2 == e


def test_tool_field_is_optional():
    """primary.tool is optional; VLM typically leaves it null, title regex fills it."""
    e = ExtractedFields(
        extractor="structured_vlm_v1_qwen36_35b",
        primary=PrimaryRegion(app="Google Chrome"),
    )
    assert e.primary.tool is None


def test_parse_from_vlm_json_response():
    """Parsing a real VLM JSON response (matching the prompt v1 contract) succeeds
    even though the VLM does not emit primary.tool."""
    raw = json.dumps({
        "primary": {
            "app": "iTerm2",
            "what": "在终端中执行 git pull",
            "title_or_topic": "hyperai-next git:(master)",
            "workspace": "hyperai-next",
        },
        "secondary": [],
        "contact": None,
        "url": None,
        "confidence": {"primary": "high", "contact": None, "url": None},
        "notes": "macOS, iTerm2 single window",
    })
    parsed = json.loads(raw)
    e = ExtractedFields(extractor="structured_vlm_v1_qwen36_35b", **parsed)
    assert e.primary.workspace == "hyperai-next"
    assert e.primary.tool is None  # VLM didn't specify; leave null


def test_confidence_value_constraints():
    """Confidence values must be in {high, medium, low, null}."""
    Confidence(primary="high")  # ok
    Confidence(primary="medium")  # ok
    Confidence(primary="low")  # ok
    Confidence(primary=None)  # ok
    with pytest.raises(ValidationError):
        Confidence(primary="extreme")  # not in enum
