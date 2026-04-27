"""Layer 1 extraction output schema. Shared by all extractors (title_regex, structured_vlm)."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class PrimaryRegion(BaseModel):
    app: str
    tool: Optional[str] = None
    what: Optional[str] = None
    title_or_topic: Optional[str] = None
    workspace: Optional[str] = None


class SecondaryRegion(BaseModel):
    app: str
    what: Optional[str] = None


class ExtractedFields(BaseModel):
    """The unified Layer 1 output. Both title_regex_v1 and structured_vlm_v1_* produce this."""
    extractor: str = Field(..., description="Identifier of the extractor and version, e.g., 'title_regex_v1' or 'structured_vlm_v1_qwen36_35b'")
    primary: PrimaryRegion
    secondary: list[SecondaryRegion] = Field(default_factory=list)
    contact: Optional[str] = None
    url: Optional[str] = None
    notes: Optional[str] = None
