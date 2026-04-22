import pytest
from memos.extractors.title_regex import extract, strip_spinner
from memos.extractors.schema import ExtractedFields


# strip_spinner unit tests: the core normalization primitive.

@pytest.mark.parametrize("raw,expected", [
    ("✳ Debug gear controller", "Debug gear controller"),
    ("⠐ Debug gear controller", "Debug gear controller"),
    ("⠂ Debug gear controller", "Debug gear controller"),
    ("◇ Debug gear controller", "Debug gear controller"),
    ("✳  Debug gear controller", "Debug gear controller"),       # double space
    ("Debug gear controller", "Debug gear controller"),           # no spinner
    ("", ""),
])
def test_strip_spinner(raw, expected):
    assert strip_spinner(raw) == expected


# The only cases extract() produces non-null fields: CC spinner + OpenCode OC|.

def test_cc_spinner_produces_tool_and_canonical_title():
    """Spinner prefix → primary.tool='Claude Code' + canonical title (stripped)."""
    result = extract("iTerm2", "✳ Debug gear controller blocking issue with bayesjob")
    assert result.extractor == "title_regex_v1"
    assert result.primary.app == "iTerm2"
    assert result.primary.tool == "Claude Code"
    assert result.primary.title_or_topic == "Debug gear controller blocking issue with bayesjob"
    # All other fields stay null (VLM's job)
    assert result.primary.workspace is None
    assert result.primary.what is None
    assert result.contact is None
    assert result.url is None


def test_cc_spinner_variants_produce_same_canonical_title():
    """Different spinner frames of the same task → identical (tool, title) identity.
    This is the whole point of title regex: TaskSession stability."""
    titles = [
        "✳ Migrate Svelte frontend to React",
        "⠐ Migrate Svelte frontend to React",
        "⠂ Migrate Svelte frontend to React",
        "◇ Migrate Svelte frontend to React",
    ]
    results = [extract("iTerm2", t) for t in titles]
    task_identities = {(r.primary.tool, r.primary.title_or_topic) for r in results}
    assert len(task_identities) == 1
    assert task_identities == {("Claude Code", "Migrate Svelte frontend to React")}


def test_opencode_oc_prefix_produces_tool_and_canonical_topic():
    """`OC | <topic>` → primary.tool='OpenCode' + canonical topic."""
    result = extract("iTerm2", "OC | Cloudflare edge auth 获取 IP 失败")
    assert result.primary.tool == "OpenCode"
    assert result.primary.title_or_topic == "Cloudflare edge auth 获取 IP 失败"
    assert result.primary.workspace is None


def test_bare_tool_name_produces_no_identity():
    """Bare 'claude' / 'codex' / 'OpenCode' (no task): app only, tool/title null."""
    for title in ["claude", "codex", "OpenCode", "tig"]:
        result = extract("iTerm2", title)
        assert result.primary.app == "iTerm2"
        assert result.primary.tool is None
        assert result.primary.title_or_topic is None


def test_non_agent_iterm_title_produces_app_only():
    """fish prompts / bash prompts / other iTerm windows: VLM's job, not title regex.
    Title regex leaves tool and title_or_topic null for these."""
    cases = [
        "fish /Users/user/projects/memos",
        "user@host:~/projects/memos",
        "[hyperai] m11",
        "kubectl get pods -w",
    ]
    for title in cases:
        result = extract("iTerm2", title)
        assert result.primary.app == "iTerm2"
        assert result.primary.tool is None
        assert result.primary.title_or_topic is None
        assert result.primary.workspace is None  # VLM's job


def test_non_iterm_app_produces_app_only():
    """Non-iTerm apps (browsers, chat, IDE, anything) → app only, all else null."""
    cases = [
        ("Google Chrome", "Some page title"),
        ("微信", "张玲"),
        ("Cursor", "library.py — memos"),
        ("Antigravity", "hyperai-next"),
    ]
    for app, title in cases:
        result = extract(app, title)
        assert result.primary.app == app
        assert result.primary.tool is None
        assert result.primary.title_or_topic is None


def test_extract_handles_none_inputs():
    """None or empty inputs do not crash."""
    result = extract(None, None)
    assert result.primary.app == ""
    assert result.primary.tool is None

    result = extract("iTerm2", None)
    assert result.primary.app == "iTerm2"
    assert result.primary.tool is None
