import asyncio
import logging
import os
from typing import Optional
import httpx
import json
import base64
from PIL import Image
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import io
import platform
import cpuinfo

MAX_THUMBNAIL_SIZE = (1920, 1920)

from fastapi import APIRouter, Request, HTTPException
from memos.schemas import Entity, MetadataType

METADATA_FIELD_NAME = "ocr_result"
PLUGIN_NAME = "ocr"

router = APIRouter(tags=[PLUGIN_NAME], responses={404: {"description": "Not found"}})
endpoint = None
token = None
concurrency = None
semaphore = None
use_local = False
ocr = None
thread_pool = None

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_metadata_name() -> str:
    """Return the metadata field name used by this plugin."""
    return METADATA_FIELD_NAME


def image2base64(img_path):
    try:
        with Image.open(img_path) as img:
            img = img.convert("RGB")
            img.thumbnail(MAX_THUMBNAIL_SIZE)
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            encoded_string = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return encoded_string
    except Exception as e:
        logger.error(f"Error processing image {img_path}: {str(e)}")
        return None


async def fetch(endpoint: str, client, image_base64, headers: Optional[dict] = None):
    async with semaphore:  # 使用信号量控制并发
        response = await client.post(
            f"{endpoint}",
            json={"image_base64": image_base64},
            timeout=60,
            headers=headers,
        )
        if response.status_code != 200:
            return None
        return response.json()


def convert_ocr_results(results):
    if results is None:
        return []
    
    converted = []
    for result in results:
        # Round each coordinate in dt_boxes to 1 decimal place
        rounded_boxes = []
        for box in result[0]:
            rounded_box = [round(coord, 1) for coord in box]
            rounded_boxes.append(rounded_box)
        
        item = {"dt_boxes": rounded_boxes, "rec_txt": result[1], "score": round(result[2], 2)}
        converted.append(item)
    return converted


def convert_ocr_data(ocr_data):
    converted_data = []
    for text, score, bbox in ocr_data:
        x_min, y_min, x_max, y_max = bbox
        # Round each coordinate to 1 decimal place
        x_min = round(x_min, 1)
        y_min = round(y_min, 1)
        x_max = round(x_max, 1)
        y_max = round(y_max, 1)
        
        dt_boxes = [
            [x_min, y_min],
            [x_max, y_min],
            [x_max, y_max],
            [x_min, y_max]
        ]
        entry = {
            'dt_boxes': dt_boxes,
            'rec_txt': text,
            'score': round(float(score), 2)
        }
        converted_data.append(entry)
    return converted_data


def predict_local(img_path):
    try:
        # Check if we should force RapidOCR for testing (set environment variable FORCE_RAPIDOCR=1)
        force_rapidocr = os.environ.get('FORCE_RAPIDOCR', '0') == '1'
        
        if platform.system() == 'Darwin' and not force_rapidocr:
            from ocrmac import ocrmac
            ocr_result = ocrmac.OCR(img_path, language_preference=['zh-Hans']).recognize(px=True)
            return convert_ocr_data(ocr_result)
        else:
            with Image.open(img_path) as img:
                img = img.convert("RGB")
                img.thumbnail(MAX_THUMBNAIL_SIZE)
                img_array = np.array(img)
            
            # Call RapidOCR and handle different return formats
            ocr_output = ocr(img_array)
            
            # Handle different RapidOCR return formats
            if isinstance(ocr_output, tuple) and len(ocr_output) == 2:
                # Old format: (results, elapsed_time)
                ocr_results, _ = ocr_output
                logger.debug("Using old tuple format")
            elif hasattr(ocr_output, '__dict__') and 'boxes' in ocr_output.__dict__ and 'txts' in ocr_output.__dict__:
                # New format: RapidOCROutput object with boxes, txts, scores attributes
                boxes = ocr_output.boxes
                txts = ocr_output.txts
                scores = ocr_output.scores if hasattr(ocr_output, 'scores') else []
                
                # Convert to the expected format: list of (box, text, score) tuples
                ocr_results = []
                for box, text, score in zip(boxes, txts, scores):
                    if score > 0.5:  # Filter by confidence
                        ocr_results.append((box, text, score))
            elif hasattr(ocr_output, 'get') and callable(ocr_output.get):
                # New format: RapidOCROutput object - try different possible keys
                for key in ['results', 'boxes', 'texts', 'data', 'content']:
                    try:
                        value = ocr_output.get(key, None)
                        if value is not None:
                            ocr_results = value
                            break
                    except Exception:
                        continue
                else:
                    # If no key worked, try empty list
                    ocr_results = []
            elif hasattr(ocr_output, '__iter__') and not isinstance(ocr_output, (str, dict, bytes)):
                # New format: RapidOCROutput object is iterable
                try:
                    ocr_results = list(ocr_output)
                except Exception:
                    ocr_results = []
            elif hasattr(ocr_output, 'results'):
                # Fallback: try to access results attribute
                ocr_results = ocr_output.results
            else:
                # Last resort: try to convert to list or return empty
                try:
                    ocr_results = list(ocr_output) if ocr_output else []
                except Exception:
                    ocr_results = []
            return convert_ocr_results(ocr_results)
    except Exception as e:
        logger.error(f"Error processing image {img_path}: {str(e)}")
        return None


async def async_predict_local(img_path):
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(thread_pool, partial(predict_local, img_path))
    return results


# Modify the predict function to use semaphore
async def predict(img_path):
    if use_local:
        return await async_predict_local(img_path)
    
    image_base64 = image2base64(img_path)
    if not image_base64:
        return None

    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token.get_secret_value()}"} if token else {}
        return await fetch(endpoint, client, image_base64, headers)


@router.get("/")
async def read_root():
    return {"healthy": True}


@router.post("", include_in_schema=False)
@router.post("/")
async def ocr(entity: Entity, request: Request):
    metadata_field_name = get_metadata_name()
    if not entity.file_type_group == "image":
        return {metadata_field_name: "{}"}

    # Check if the metadata field already exists and has a non-empty value
    existing_metadata = entity.get_metadata_by_key(metadata_field_name)
    if existing_metadata and existing_metadata.value and existing_metadata.value.strip():
        logger.info(f"Skipping OCR processing for file: {entity.filepath} due to existing metadata")
        return {metadata_field_name: existing_metadata.value}

    # Check if the entity contains the tag "low_info"
    if any(tag.name == "low_info" for tag in entity.tags):
        logger.info(f"Skipping OCR processing for file: {entity.filepath} due to 'low_info' tag")
        return {metadata_field_name: "{}"}

    location_url = request.headers.get("Location")
    if not location_url:
        raise HTTPException(status_code=400, detail="Location header is missing")

    patch_url = f"{location_url}/metadata"

    ocr_result = await predict(entity.filepath)
    if ocr_result:
        filtered_results = [r for r in ocr_result if r['score'] > 0.5][:10]
        texts = [f"{r['rec_txt']}({r['score']:.2f})" for r in filtered_results]
        total = len(ocr_result)
        logger.info(f"First {len(texts)}/{total} OCR results: {texts}")
    else:
        logger.info(f"No OCR result found for file: {entity.filepath}")
        return {metadata_field_name: "{}"}

    # Call the URL to patch the entity's metadata
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            patch_url,
            json={
                "metadata_entries": [
                    {
                        "key": metadata_field_name,
                        "value": json.dumps(
                            ocr_result,
                            default=lambda o: o.item() if hasattr(o, "item") else o,
                        ),
                        "source": PLUGIN_NAME,
                        "data_type": MetadataType.JSON_DATA.value,
                    }
                ]
            },
            timeout=30,
        )

    # Check if the patch request was successful
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code, detail="Failed to patch entity metadata"
        )

    return {
        metadata_field_name: json.dumps(
            ocr_result,
            default=lambda o: o.item() if hasattr(o, "item") else o,
        )
    }


def init_plugin(config):
    global endpoint, token, concurrency, semaphore, use_local, ocr, thread_pool
    endpoint = config.endpoint
    token = config.token
    concurrency = config.concurrency
    use_local = config.use_local
    semaphore = asyncio.Semaphore(concurrency)
    
    if use_local:
        from rapidocr import RapidOCR
        config_params = {
            "Global.width_height_ratio": 40,
        }        
        
        # Initialize RapidOCR with simplified configuration
        # The library will use default values for detection, classification, and recognition
        ocr = RapidOCR(params=config_params)
            
        thread_pool = ThreadPoolExecutor(max_workers=concurrency)

    logger.info("OCR plugin initialized")
    logger.info(f"Endpoint: {endpoint}")
    logger.info(f"Token: {token}")
    logger.info(f"Concurrency: {concurrency}")
    logger.info(f"Use local: {use_local}")
    if use_local:
        logger.info(f"OCR library: {'rapidocr_openvino' if platform.system() == 'Windows' and 'Intel' in cpuinfo.get_cpu_info()['brand_raw'] else 'rapidocr_onnxruntime'}")
