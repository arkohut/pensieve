"""Structured VLM plugin for Pensieve.

Calls a VLM endpoint with the v1 structured prompt and stores the parsed
result as `structured_vlm_v1_<modelname>` metadata on each entity.

Mirrors the existing `vlm/` plugin shape (FastAPI app, init_plugin, POST handler).
"""
from __future__ import annotations
import asyncio
import base64
import io
import json
import logging
import re
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from PIL import Image

from memos.extractors.schema import ExtractedFields
from memos.plugins.structured_vlm.prompt_v1 import PROMPT_TEXT, PROMPT_VERSION
from memos.schemas import Entity, MetadataType

logger = logging.getLogger(__name__)
PLUGIN_NAME = "structured_vlm"

router = APIRouter(tags=[PLUGIN_NAME], responses={404: {"description": "Not found"}})

# Module-level config, populated by init_plugin()
modelname: Optional[str] = None
endpoint: Optional[str] = None
token = None
concurrency: int = 4
force_jpeg: bool = True
max_tokens: int = 2048
disable_thinking: bool = True
semaphore: Optional[asyncio.Semaphore] = None


def metadata_field_name(modelname: str) -> str:
    """Versioned metadata key per (prompt_version, model). Same model -> same key."""
    safe_model = re.sub(r"[^A-Za-z0-9]", "_", modelname).lower()
    return f"structured_vlm_{PROMPT_VERSION}_{safe_model}"


def _image_to_base64(img_path: str, max_width: int = 1600, quality: int = 85) -> Optional[str]:
    """Open, downscale if needed, return base64 JPEG."""
    try:
        img = Image.open(img_path)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        logger.warning(f"Failed to load image {img_path}: {e}")
        return None


def _parse_json_loose(text: str) -> Optional[dict]:
    """Try direct parse, then markdown-stripped, then first {..} block."""
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def parse_vlm_response_to_extracted(raw_text: str, modelname: str) -> Optional[ExtractedFields]:
    """Parse the VLM's text response into an ExtractedFields. Returns None if unrecoverable."""
    parsed = _parse_json_loose(raw_text)
    if not parsed:
        return None
    try:
        return ExtractedFields(extractor=metadata_field_name(modelname), **parsed)
    except Exception as e:
        logger.warning(f"VLM JSON does not match ExtractedFields schema: {e}; raw: {raw_text[:200]}")
        return None


async def predict_structured(
    endpoint: str, modelname: str, img_path: str,
    token: Optional[object] = None, max_tokens: int = 2048,
    disable_thinking: bool = True,
) -> Optional[ExtractedFields]:
    """Call VLM endpoint, return ExtractedFields or None on failure."""
    img_b64 = _image_to_base64(img_path)
    if not img_b64:
        return None
    request_data = {
        "model": modelname,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                {"type": "text", "text": PROMPT_TEXT},
            ],
        }],
        "stream": False,
        "max_tokens": max_tokens,
        "temperature": 0.1,
        "top_p": 0.8,
    }
    if disable_thinking:
        request_data["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
    headers = {"Content-Type": "application/json"}
    if token is not None:
        # Token may be a SecretStr (pydantic) or plain str
        token_str = token.get_secret_value() if hasattr(token, "get_secret_value") else str(token)
        if token_str:
            headers["Authorization"] = f"Bearer {token_str}"

    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                f"{endpoint.rstrip('/')}/v1/chat/completions",
                headers=headers, json=request_data, timeout=180.0,
            )
            r.raise_for_status()
            data = r.json()
            raw_text = data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"VLM call failed for {img_path}: {e}")
            return None

    return parse_vlm_response_to_extracted(raw_text, modelname)


@router.get("/")
async def read_root():
    return {"healthy": True, "plugin": PLUGIN_NAME, "model": modelname,
            "prompt_version": PROMPT_VERSION}


@router.post("", include_in_schema=False)
@router.post("/")
async def handle_entity(entity: Entity, request: Request):
    """Plugin webhook: process entity, write metadata back."""
    if entity.file_type_group != "image":
        return {}
    field = metadata_field_name(modelname)
    existing = entity.get_metadata_by_key(field)
    if existing and existing.value and existing.value.strip():
        logger.info(f"Skip {entity.filepath}: already has {field}")
        return {field: existing.value}

    location_url = request.headers.get("Location")
    if not location_url:
        raise HTTPException(status_code=400, detail="Location header is missing")

    async with semaphore:
        result = await predict_structured(
            endpoint=endpoint, modelname=modelname,
            img_path=entity.filepath, token=token,
            max_tokens=max_tokens, disable_thinking=disable_thinking,
        )

    if result is None:
        raise HTTPException(
            status_code=502,
            detail=f"structured VLM call or parse failed for {entity.filepath}",
        )

    value = result.model_dump_json()
    patch_url = f"{location_url}/metadata"
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            patch_url,
            json={"metadata_entries": [{
                "key": field, "value": value,
                "source": PLUGIN_NAME, "data_type": MetadataType.TEXT_DATA.value,
            }]},
            timeout=30,
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Failed to patch metadata")
    return {field: value}


def init_plugin(config) -> None:
    global modelname, endpoint, token, concurrency, force_jpeg, max_tokens, disable_thinking, semaphore
    modelname = config.modelname
    endpoint = config.endpoint
    token = config.token
    concurrency = config.concurrency
    force_jpeg = config.force_jpeg
    max_tokens = config.max_tokens
    disable_thinking = config.disable_thinking
    semaphore = asyncio.Semaphore(concurrency)
    logger.info(f"structured_vlm plugin initialized: model={modelname}, "
                f"prompt={PROMPT_VERSION}, max_tokens={max_tokens}, "
                f"disable_thinking={disable_thinking}")
