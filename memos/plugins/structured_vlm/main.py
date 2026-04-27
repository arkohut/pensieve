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

# Failure categories for log triage. Server-side (transient): http_5xx, network.
# Client/data-side (terminal): image_load, http_4xx, empty, json_parse, schema.
FAIL_IMAGE_LOAD = "image_load"
FAIL_HTTP_4XX = "http_4xx"
FAIL_HTTP_5XX = "http_5xx"
FAIL_NETWORK = "network"
FAIL_EMPTY = "empty"
FAIL_JSON_PARSE = "json_parse"
FAIL_SCHEMA = "schema_validation"

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


def parse_vlm_response_to_extracted(
    raw_text: str, modelname: str, log_ctx: str = "",
) -> Optional[ExtractedFields]:
    """Parse the VLM's text response into an ExtractedFields. Returns None if unrecoverable."""
    if not raw_text or not raw_text.strip():
        logger.warning(f"VLM fail category={FAIL_EMPTY} {log_ctx}")
        return None
    parsed = _parse_json_loose(raw_text)
    if parsed is None:
        logger.warning(
            f"VLM fail category={FAIL_JSON_PARSE} raw={raw_text[:200]!r} {log_ctx}"
        )
        return None
    try:
        return ExtractedFields(extractor=metadata_field_name(modelname), **parsed)
    except Exception as e:
        logger.warning(
            f"VLM fail category={FAIL_SCHEMA} err={e} raw={raw_text[:200]!r} {log_ctx}"
        )
        return None


async def predict_structured(
    endpoint: str, modelname: str, img_path: str,
    token: Optional[object] = None, max_tokens: int = 2048,
    disable_thinking: bool = True,
    entity_id: Optional[int] = None,
    max_retries: int = 3,
    retry_base_delay: float = 0.5,
) -> Optional[ExtractedFields]:
    """Call VLM endpoint, return ExtractedFields or None on failure.

    Retries on transient errors only (5xx and network/timeout). 4xx, image-load,
    and parse failures are terminal and return None immediately. Every failure
    path emits one structured warning with `category=...` so log triage can
    distinguish server-side (http_5xx, network) from data/client-side (image_load,
    http_4xx, empty, json_parse, schema_validation) issues.
    """
    log_ctx = f"entity_id={entity_id} path={img_path}"

    img_b64 = _image_to_base64(img_path)
    if not img_b64:
        logger.warning(f"VLM fail category={FAIL_IMAGE_LOAD} {log_ctx}")
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
        token_str = token.get_secret_value() if hasattr(token, "get_secret_value") else str(token)
        if token_str:
            headers["Authorization"] = f"Bearer {token_str}"

    url = f"{endpoint.rstrip('/')}/v1/chat/completions"
    raw_text: Optional[str] = None
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(url, headers=headers, json=request_data, timeout=180.0)
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as e:
            if attempt < max_retries - 1:
                delay = retry_base_delay * (2 ** attempt)
                logger.info(
                    f"VLM transient network error, retry {attempt+1}/{max_retries} "
                    f"after {delay:.1f}s err={e} {log_ctx}"
                )
                await asyncio.sleep(delay)
                continue
            logger.warning(f"VLM fail category={FAIL_NETWORK} err={e} {log_ctx}")
            return None

        if r.status_code == 200:
            try:
                data = r.json()
                raw_text = data["choices"][0]["message"]["content"]
            except Exception as e:
                logger.warning(
                    f"VLM fail category={FAIL_EMPTY} err=malformed_envelope:{e} "
                    f"body={r.text[:200]!r} {log_ctx}"
                )
                return None
            break
        if 500 <= r.status_code < 600:
            if attempt < max_retries - 1:
                delay = retry_base_delay * (2 ** attempt)
                logger.info(
                    f"VLM transient {r.status_code}, retry {attempt+1}/{max_retries} "
                    f"after {delay:.1f}s body={r.text[:200]!r} {log_ctx}"
                )
                await asyncio.sleep(delay)
                continue
            logger.warning(
                f"VLM fail category={FAIL_HTTP_5XX} status={r.status_code} "
                f"body={r.text[:200]!r} {log_ctx}"
            )
            return None
        # 4xx is terminal — no point retrying auth / payload errors.
        logger.warning(
            f"VLM fail category={FAIL_HTTP_4XX} status={r.status_code} "
            f"body={r.text[:200]!r} {log_ctx}"
        )
        return None

    if raw_text is None:
        logger.warning(f"VLM fail category={FAIL_NETWORK} err=exhausted_retries {log_ctx}")
        return None

    return parse_vlm_response_to_extracted(raw_text, modelname, log_ctx=log_ctx)


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
            entity_id=entity.id,
        )

    if result is None:
        # Failure category was already logged by predict_structured. Tail the
        # plugin log (`grep "VLM fail category="`) to triage server vs. client.
        raise HTTPException(
            status_code=502,
            detail=f"structured VLM failed for entity_id={entity.id} (see plugin log)",
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
