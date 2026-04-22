"""Versioned prompt asset for structured VLM extraction.

The prompt text lives in prompt_v1.txt as a sibling file so it is easy to
inspect / version-control / diff. The version string is part of the metadata
field name, so prompt changes always get a new field rather than overwriting.
"""
from pathlib import Path

PROMPT_VERSION = "v1"

_THIS_DIR = Path(__file__).parent
PROMPT_TEXT = (_THIS_DIR / "prompt_v1.txt").read_text(encoding="utf-8")
