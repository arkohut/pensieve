"""Layer 1 extraction output schema. Shared by all extractors (title_regex, structured_vlm)."""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field

ConfidenceLevel = Literal["high", "medium", "low"]


class PrimaryRegion(BaseModel):
    app: str
    # Tool is the AI CLI running inside iTerm, when identifiable: "Claude Code" or "OpenCode".
    # VLM leaves this null; title_regex_v1 fills it when spinner/prefix is recognized.
    # Used by Layer 2 to form TaskSession identity key (tool, title_or_topic).
    tool: Optional[str] = None
    what: Optional[str] = None
    title_or_topic: Optional[str] = None
    workspace: Optional[str] = None


class SecondaryRegion(BaseModel):
    app: str
    what: Optional[str] = None


class Confidence(BaseModel):
    primary: Optional[ConfidenceLevel] = None
    contact: Optional[ConfidenceLevel] = None
    url: Optional[ConfidenceLevel] = None


class ExtractedFields(BaseModel):
    """The unified Layer 1 output. Both title_regex_v1 and structured_vlm_v1_* produce this."""
    extractor: str = Field(..., description="Identifier of the extractor and version, e.g., 'title_regex_v1' or 'structured_vlm_v1_qwen36_35b'")
    primary: PrimaryRegion
    secondary: list[SecondaryRegion] = Field(default_factory=list)
    contact: Optional[str] = None
    url: Optional[str] = None
    confidence: Confidence = Field(default_factory=Confidence)
    notes: Optional[str] = None
