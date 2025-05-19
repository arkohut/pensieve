import os
import httpx
import uvicorn
import mimetypes
import time
import threading
import psutil
from datetime import datetime, timedelta

import logfire

from fastapi import FastAPI, HTTPException, Depends, status, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker
from typing import List, Annotated
from pathlib import Path
import json
import cv2
from PIL import Image
import logging
from urllib.parse import quote

from .config import settings, load_config, save_config, apply_config_updates, restart_processes
from memos.plugins.vlm import main as vlm_main
from memos.plugins.ocr import main as ocr_main
from . import crud
from .search import create_search_provider
from .read_metadata import read_metadata
from .schemas import (
    Library,
    Folder,
    Entity,
    Plugin,
    NewLibraryParam,
    NewFoldersParam,
    NewEntityParam,
    UpdateEntityParam,
    NewPluginParam,
    NewLibraryPluginParam,
    UpdateEntityTagsParam,
    UpdateEntityMetadataParam,
    MetadataType,
    MetadataIndexItem,
    EntitySearchResult,
    SearchResult,
    SearchHit,
    RequestParams,
    EntityContext,
    BatchIndexRequest,
    FacetCount,
    Facet,
    FacetStats,
)
from .logging_config import LOGGING_CONFIG
from .databases.initializers import create_db_initializer

# Configure logging
logging.basicConfig(level=logging.INFO)

# Configure mimetypes for JavaScript files
# This is a workaround for the issue:
# https://github.com/python/cpython/issues/88141#issuecomment-1631735902
# Without this, the mime type of .js files will be text/plain and
# the browser will not render them correctly in some windows machines.
mimetypes.add_type("application/javascript", ".js")

app = FastAPI()

logfire.configure(send_to_logfire="if-token-present")
logfire.instrument_fastapi(app, excluded_urls=["/files"])

# Create database engine and initializer
engine, initializer = create_db_initializer(settings)

# Initialize search provider based on database URL
search_provider = create_search_provider(settings.database_url)
app.state.search_provider = search_provider

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

logfire.instrument_sqlalchemy(engine=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create API router with prefix
api_router = FastAPI()

current_dir = os.path.dirname(__file__)

app.mount(
    "/_app", StaticFiles(directory=os.path.join(current_dir, "static/_app"), html=True)
)

# Mount API router with prefix
app.mount("/api", api_router)

@api_router.get("/health")
async def health():
    return {"status": "ok"}


@api_router.get("/processes", tags=["system"])
async def get_processes():
    """获取当前所有服务进程的状态"""
    services = ["serve", "watch", "record"]
    processes = []

    for service in services:
        service_processes = [
            p
            for p in psutil.process_iter(["pid", "name", "cmdline", "create_time"])
            if "python" in p.info["name"].lower()
            and p.info["cmdline"] is not None
            and "memos.commands" in p.info["cmdline"]
            and service in p.info["cmdline"]
        ]

        if service_processes:
            for process in service_processes:
                create_time = datetime.fromtimestamp(
                    process.info["create_time"]
                ).strftime("%Y-%m-%d %H:%M:%S")
                running_time = str(
                    timedelta(seconds=int(time.time() - process.info["create_time"]))
                )
                processes.append({
                    "name": service,
                    "status": "Running",
                    "pid": process.info["pid"],
                    "startedAt": create_time,
                    "runningFor": running_time
                })
        else:
            processes.append({
                "name": service,
                "status": "Not Running",
                "pid": "-",
                "startedAt": "-",
                "runningFor": "-"
            })

    return {"processes": processes}


@app.get("/favicon.png", response_class=FileResponse)
async def favicon_png():
    return FileResponse(os.path.join(current_dir, "static/favicon.png"))


@app.get("/favicon.ico", response_class=FileResponse)
async def favicon_ico():
    return FileResponse(os.path.join(current_dir, "static/favicon.png"))


@app.get("/")
async def serve_spa():
    return FileResponse(os.path.join(current_dir, "static/app.html"))

# Add catch-all route for SPA
@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    # Skip if the path starts with /api or /_app
    if full_path.startswith(("api/", "_app/")):
        raise HTTPException(status_code=404, detail="Not found")
    
    # For all other paths, serve the SPA
    return FileResponse(os.path.join(current_dir, "static/app.html"))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@api_router.post("/libraries", response_model=Library, tags=["library"])
def new_library(library_param: NewLibraryParam, db: Session = Depends(get_db)):
    # Check if a library with the same name (case insensitive) already exists
    existing_library = crud.get_library_by_name(library_param.name, db)
    if existing_library:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Library with this name already exists",
        )

    # Remove duplicate folders from the library_param
    unique_folders = []
    seen_paths = set()
    for folder in library_param.folders:
        if folder.path not in seen_paths:
            seen_paths.add(folder.path)
            unique_folders.append(folder)
    library_param.folders = unique_folders

    library = crud.create_library(library_param, db)
    return library

@api_router.get("/libraries", response_model=List[Library], tags=["library"])
def list_libraries(db: Session = Depends(get_db)):
    libraries = crud.get_libraries(db)
    return libraries

@api_router.get("/libraries/{library_id}", response_model=Library, tags=["library"])
def get_library_by_id(library_id: int, db: Session = Depends(get_db)):
    library = crud.get_library_by_id(library_id, db)
    if library is None:
        return JSONResponse(
            content={"detail": "Library not found"},
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return library

@api_router.post("/libraries/{library_id}/folders", response_model=Library, tags=["library"])
def new_folders(
    library_id: int,
    folders: NewFoldersParam,
    db: Session = Depends(get_db),
):
    library = crud.get_library_by_id(library_id, db)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Library not found"
        )

    existing_folders = [folder.path for folder in library.folders]
    if any(str(folder.path) in existing_folders for folder in folders.folders):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Folder already exists in the library",
        )

    return crud.add_folders(library_id=library.id, folders=folders, db=db)


async def trigger_webhooks(
    library: Library,
    entity: Entity,
    request: Request,
    plugins: List[int] = None,
    db: Session = Depends(get_db),
):
    """Trigger webhooks for plugins that haven't processed the entity yet"""
    async with httpx.AsyncClient() as client:
        tasks = []
        pending_plugins = crud.get_pending_plugins(entity.id, library.id, db)

        for plugin in library.plugins:
            # Skip if specific plugins are requested and this one isn't in the list
            if plugins is not None and plugin.id not in plugins:
                continue

            # Skip if entity has already been processed by this plugin
            if plugin.id not in pending_plugins:
                continue

            if plugin.webhook_url:
                logging.info("Triggering plugin %d for entity %d", plugin.id, entity.id)
                location = str(request.url_for("get_entity_by_id", entity_id=entity.id))
                webhook_url = plugin.webhook_url
                if webhook_url.startswith("/"):
                    webhook_url = str(request.base_url)[:-1] + webhook_url
                task = client.post(
                    webhook_url,
                    json=entity.model_dump(mode="json"),
                    headers={"Location": location},
                    timeout=300.0,
                )
                tasks.append((plugin.id, task))

        for plugin_id, task in tasks:
            try:
                response = await task
                if response.status_code < 400:
                    # Record successful plugin processing
                    crud.record_plugin_processed(entity.id, plugin_id, db)
                else:
                    logging.error(
                        "Error processing entity with plugin %d: %d - %s",
                        plugin_id,
                        response.status_code,
                        response.text,
                    )
            except Exception as e:
                logging.error(
                    "Error processing entity with plugin %d: %s",
                    plugin_id,
                    str(e),
                )

@api_router.post("/libraries/{library_id}/entities", response_model=Entity, tags=["entity"])
async def new_entity(
    new_entity: NewEntityParam,
    library_id: int,
    request: Request,
    db: Session = Depends(get_db),
    plugins: Annotated[List[int] | None, Query()] = None,
    trigger_webhooks_flag: bool = True,
    update_index: bool = False,
    search_provider=Depends(lambda: app.state.search_provider),
):
    library = crud.get_library_by_id(library_id, db)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Library not found"
        )

    with logfire.span("create new entity {filepath=}", filepath=new_entity.filepath):
        entity = crud.create_entity(library_id, new_entity, db)

    if trigger_webhooks_flag:
        with logfire.span("trigger webhooks {entity_id=}", entity_id=entity.id):
            await trigger_webhooks(library, entity, request, plugins, db)

    if update_index:
        with logfire.span("update entity index {entity_id=}", entity_id=entity.id):
            search_provider.update_entity_index(entity.id, db)

    return entity

@api_router.get(
    "/libraries/{library_id}/folders/{folder_id}/entities",
    response_model=List[Entity],
    tags=["entity"],
)
def list_entities_in_folder(
    library_id: int,
    folder_id: int,
    limit: Annotated[int, Query(ge=1, le=400)] = 10,
    offset: int = 0,
    path_prefix: str | None = None,
    unprocessed_only: bool = False,
    order_by: str = Query("last_scan_at:desc", pattern="^[a-zA-Z_]+:(asc|desc)$"),
    db: Session = Depends(get_db),
):
    library = crud.get_library_by_id(library_id, db)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Library not found"
        )

    if folder_id not in [folder.id for folder in library.folders]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found in the specified library",
        )

    try:
        entities, total_count = crud.get_entities_of_folder(
            library_id,
            folder_id,
            db,
            limit,
            offset,
            path_prefix,
            unprocessed_only,
            order_by,
        )
        return JSONResponse(
            content=jsonable_encoder(entities),
            headers={"X-Total-Count": str(total_count)},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@api_router.get(
    "/libraries/{library_id}/entities/by-filepath",
    response_model=Entity,
    tags=["entity"],
)
def get_entity_by_filepath(
    library_id: int, filepath: str, db: Session = Depends(get_db)
):
    entity = crud.get_entity_by_filepath(filepath, db)
    if entity is None or entity.library_id != library_id:
        return JSONResponse(
            content={"detail": "Entity not found"},
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return entity

@api_router.post(
    "/libraries/{library_id}/entities/by-filepaths",
    response_model=List[Entity],
    tags=["entity"],
)
def get_entities_by_filepaths(
    library_id: int, filepaths: List[str], db: Session = Depends(get_db)
):
    entities = crud.get_entities_by_filepaths(filepaths, db)
    return [entity for entity in entities if entity.library_id == library_id]

@api_router.get("/entities/{entity_id}", response_model=Entity, tags=["entity"])
def get_entity_by_id(entity_id: int, db: Session = Depends(get_db)):
    entity = crud.get_entity_by_id(entity_id, db, include_relationships=True)
    if entity is None:
        return JSONResponse(
            content={"detail": "Entity not found"},
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return entity

@api_router.get(
    "/libraries/{library_id}/entities/{entity_id}",
    response_model=Entity,
    tags=["entity"],
)
def get_entity_by_id_in_library(
    library_id: int, entity_id: int, db: Session = Depends(get_db)
):
    entity = crud.get_entity_by_id(entity_id, db, include_relationships=True)
    if entity is None or entity.library_id != library_id:
        return JSONResponse(
            content={"detail": "Entity not found"},
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return entity

@api_router.put("/entities/{entity_id}", response_model=Entity, tags=["entity"])
async def update_entity(
    entity_id: int,
    request: Request,
    updated_entity: UpdateEntityParam = None,
    db: Session = Depends(get_db),
    trigger_webhooks_flag: bool = False,
    plugins: Annotated[List[int] | None, Query()] = None,
    update_index: bool = False,
    force: bool = False,
    search_provider=Depends(lambda: app.state.search_provider),
):
    with logfire.span("fetch entity {entity_id=}", entity_id=entity_id):
        entity = crud.get_entity_by_id(entity_id, db)
        if entity is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entity not found",
            )

    if updated_entity:
        entity = crud.update_entity(entity_id, updated_entity, db, force=(force if trigger_webhooks_flag else False))

    if trigger_webhooks_flag:
        library = crud.get_library_by_id(entity.library_id, db)
        if library is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Library not found"
            )
        await trigger_webhooks(library, entity, request, plugins, db)

    if update_index:
        search_provider.update_entity_index(entity.id, db)

    return entity

@api_router.post(
    "/entities/{entity_id}/last-scan-at",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["entity"],
)
def update_entity_last_scan_at(entity_id: int, db: Session = Depends(get_db)):
    """
    Update the last_scan_at timestamp for an entity and trigger update for fts and vec.
    """
    succeeded = crud.touch_entity(entity_id, db)
    if not succeeded:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )

@api_router.post(
    "/entities/{entity_id}/index",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["entity"],
)
def update_index(
    entity_id: int,
    db: Session = Depends(get_db),
    search_provider=Depends(lambda: app.state.search_provider),
):
    """
    Update the FTS and vector indexes for an entity.
    """
    entity = crud.get_entity_by_id(entity_id, db)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )

    search_provider.update_entity_index(entity.id, db)

@api_router.post(
    "/entities/batch-index",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["entity"],
)
async def batch_update_index(
    request: BatchIndexRequest,
    db: Session = Depends(get_db),
    search_provider=Depends(lambda: app.state.search_provider),
):
    """
    Batch update the FTS and vector indexes for multiple entities.
    """
    try:
        search_provider.batch_update_entity_indices(request.entity_ids, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@api_router.put("/entities/{entity_id}/tags", response_model=Entity, tags=["entity"])
def replace_entity_tags(
    entity_id: int, update_tags: UpdateEntityTagsParam, db: Session = Depends(get_db)
):
    entity = crud.get_entity_by_id(entity_id, db)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )

    return crud.update_entity_tags(entity_id, update_tags.tags, db)

@api_router.patch("/entities/{entity_id}/tags", response_model=Entity, tags=["entity"])
def patch_entity_tags(
    entity_id: int, update_tags: UpdateEntityTagsParam, db: Session = Depends(get_db)
):
    entity = crud.get_entity_by_id(entity_id, db)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )

    return crud.add_new_tags(entity_id, update_tags.tags, db)

@api_router.patch("/entities/{entity_id}/metadata", response_model=Entity, tags=["entity"])
def patch_entity_metadata(
    entity_id: int,
    update_metadata: UpdateEntityMetadataParam,
    db: Session = Depends(get_db),
):
    with logfire.span("fetch entity {entity_id=}", entity_id=entity_id):
        entity = crud.get_entity_by_id(entity_id, db)
        if entity is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entity not found",
            )

    # Use the CRUD function to update the metadata entries
    entity = crud.update_entity_metadata_entries(
        entity_id, update_metadata.metadata_entries, db
    )
    return entity

@api_router.delete(
    "/libraries/{library_id}/entities/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["entity"],
)
def remove_entity(library_id: int, entity_id: int, db: Session = Depends(get_db)):
    entity = crud.get_entity_by_id(entity_id, db)
    if entity is None or entity.library_id != library_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found in the specified library",
        )

    crud.remove_entity(entity_id, db)

@api_router.post("/plugins", response_model=Plugin, tags=["plugin"])
def new_plugin(new_plugin: NewPluginParam, db: Session = Depends(get_db)):
    existing_plugin = crud.get_plugin_by_name(new_plugin.name, db)
    if existing_plugin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plugin with this name already exists",
        )
    plugin = crud.create_plugin(new_plugin, db)
    return plugin

@api_router.get("/plugins", response_model=List[Plugin], tags=["plugin"])
def list_plugins(db: Session = Depends(get_db)):
    plugins = crud.get_plugins(db)
    return plugins

@api_router.post(
    "/libraries/{library_id}/plugins",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["plugin"],
)
def add_library_plugin(
    library_id: int, new_plugin: NewLibraryPluginParam, db: Session = Depends(get_db)
):
    library = crud.get_library_by_id(library_id, db)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Library not found"
        )

    plugin = None
    if new_plugin.plugin_id is not None:
        plugin = crud.get_plugin_by_id(new_plugin.plugin_id, db)
    elif new_plugin.plugin_name is not None:
        plugin = crud.get_plugin_by_name(new_plugin.plugin_name, db)

    if plugin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found"
        )

    if any(p.id == plugin.id for p in library.plugins):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plugin already exists in the library",
        )

    crud.add_plugin_to_library(library_id, plugin.id, db)

@api_router.delete(
    "/libraries/{library_id}/plugins/{plugin_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["plugin"],
)
def delete_library_plugin(
    library_id: int, plugin_id: int, db: Session = Depends(get_db)
):
    library = crud.get_library_by_id(library_id, db)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Library not found"
        )

    plugin = crud.get_plugin_by_id(plugin_id, db)
    if plugin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found"
        )

    crud.remove_plugin_from_library(library_id, plugin_id, db)


def is_image(file_path: Path) -> bool:
    return file_path.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]


def get_thumbnail_info(metadata: dict) -> tuple:
    if not metadata:
        return None, None, None

    if not metadata.get("sequence"):
        return None, None, False

    return metadata.get("screen_name"), metadata.get("sequence"), True


def extract_video_frame(video_path: Path, frame_number: int) -> Image.Image:
    cap = cv2.VideoCapture(str(video_path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        return None

    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return Image.fromarray(frame_rgb)


def generate_thumbnail(image_path: Path, size: tuple = (400, 400)) -> Path:
    """Generate a thumbnail for an image and cache it in /tmp"""
    try:
        # Create a unique thumbnail filename based on original path and size
        # Include file modification time in the filename to handle updated images
        mtime = int(image_path.stat().st_mtime)
        thumb_filename = (
            f"thumb_{image_path.name}_{size[0]}x{size[1]}_{mtime}{image_path.suffix}"
        )
        thumb_path = Path("/tmp") / thumb_filename

        # If thumbnail already exists, return it
        if thumb_path.exists():
            return thumb_path

        # Generate the thumbnail
        img = Image.open(image_path)

        # Use LANCZOS resampling for better quality
        img.thumbnail(size, Image.LANCZOS)

        # Save the thumbnail with optimized settings
        thumb_path.parent.mkdir(parents=True, exist_ok=True)

        # Use appropriate quality/optimization settings based on image format
        if image_path.suffix.lower() in [".jpg", ".jpeg"]:
            img.save(thumb_path, quality=85, optimize=True)
        elif image_path.suffix.lower() == ".png":
            img.save(thumb_path, optimize=True)
        elif image_path.suffix.lower() == ".webp":
            img.save(thumb_path, format="WEBP", quality=85)
        else:
            img.save(thumb_path)

        return thumb_path
    except Exception as e:
        logging.error(f"Error generating thumbnail for {image_path}: {e}")
        return None


def cleanup_thumbnails(max_age_days=365):
    """Clean up thumbnails older than max_age_days"""
    try:
        thumbnail_dir = Path("/tmp")
        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 60 * 60

        # Find and remove old thumbnail files
        count = 0
        for file_path in thumbnail_dir.glob("thumb_*"):
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    file_path.unlink()
                    count += 1

        logging.info(f"Cleaned up {count} old thumbnail files")
    except Exception as e:
        logging.error(f"Error cleaning up thumbnails: {e}")


def schedule_thumbnail_cleanup(interval_hours=24):
    """Schedule periodic thumbnail cleanup"""

    def cleanup_task():
        while True:
            time.sleep(interval_hours * 60 * 60)
            cleanup_thumbnails()

    # Start the cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
    cleanup_thread.start()
    logging.info(f"Scheduled thumbnail cleanup every {interval_hours} hours")

@api_router.get("/files/video/{file_path:path}", tags=["files"])
async def get_video_frame(file_path: str):

    full_path = Path("/") / file_path.strip("/")

    if not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    if not is_image(full_path):
        return FileResponse(full_path)

    metadata = read_metadata(str(full_path))
    screen, sequence, is_thumbnail = get_thumbnail_info(metadata)

    logging.debug(
        "Screen: %s, Sequence: %s, Is Thumbnail: %s", screen, sequence, is_thumbnail
    )

    if not all([screen, sequence, is_thumbnail]):
        return FileResponse(full_path)

    video_path = full_path.parent / f"{screen}.mp4"
    logging.debug("Video path: %s", video_path)
    if not video_path.is_file():
        return FileResponse(full_path)

    frame_image = extract_video_frame(video_path, sequence)
    if frame_image is None:
        return FileResponse(full_path)

    temp_dir = Path("/tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"temp_{full_path.name}"
    frame_image.save(temp_path)

    return FileResponse(
        temp_path, headers={"Content-Disposition": f"inline; filename={full_path.name}"}
    )

@api_router.get("/files/{file_path:path}", tags=["files"])
async def get_file(file_path: str):
    full_path = Path("/") / file_path.strip("/")
    # Check if the file exists and is a file
    if full_path.is_file():
        return FileResponse(full_path)
    else:
        return JSONResponse(
            content={"detail": "File not found"}, status_code=status.HTTP_404_NOT_FOUND
        )

@api_router.get("/thumbnails/{file_path:path}", tags=["files"])
async def get_thumbnail(file_path: str, width: int = 200, height: int = 200):
    """Dedicated endpoint for thumbnails to make it easier for clients"""
    full_path = Path("/") / file_path.strip("/")

    # Check if the file exists and is a file
    if not full_path.is_file():
        return JSONResponse(
            content={"detail": "File not found"}, status_code=status.HTTP_404_NOT_FOUND
        )

    # Only generate thumbnails for images
    if not is_image(full_path):
        return JSONResponse(
            content={"detail": "Thumbnails only supported for images"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Generate the thumbnail
    thumb_path = generate_thumbnail(full_path, (width, height))
    if thumb_path:
        filename = f"thumb_{full_path.name}"
        # Use RFC 6266/5987 for UTF-8 filename support
        disposition = (
            f"inline; filename=thumb.png; filename*=UTF-8''{quote(filename)}"
        )
        return FileResponse(
            thumb_path,
            headers={"Content-Disposition": disposition},
        )
    else:
        # Fallback to original file if thumbnail generation fails
        return FileResponse(full_path)

@api_router.get("/search", response_model=SearchResult, tags=["search"])
async def search_entities_v2(
    q: str,
    library_ids: str = Query(None, description="Comma-separated list of library IDs"),
    limit: Annotated[int, Query(ge=1, le=200)] = 48,
    start: int = None,
    end: int = None,
    app_names: str = Query(None, description="Comma-separated list of app names"),
    facet: bool = Query(None, description="Include facet in the search results"),
    db: Session = Depends(get_db),
    search_provider=Depends(lambda: app.state.search_provider),
):
    library_ids = [int(id) for id in library_ids.split(",")] if library_ids else None
    app_name_list = (
        [app_name.strip() for app_name in app_names.split(",")] if app_names else None
    )

    # Use settings.facet if facet parameter is not provided
    use_facet = settings.facet if facet is None else facet

    try:
        if q.strip() == "":
            # Use list_entities when q is empty
            entities = crud.list_entities(
                db=db, limit=limit, library_ids=library_ids, start=start, end=end
            )
            stats = {}
        else:
            # Use search provider for both search and stats
            entity_ids = search_provider.hybrid_search(
                query=q,
                db=db,
                limit=limit,
                library_ids=library_ids,
                start=start,
                end=end,
                app_names=app_name_list,
            )
            entities = crud.find_entities_by_ids(entity_ids, db)
            stats = (
                search_provider.get_search_stats(
                    query=q,
                    db=db,
                    library_ids=library_ids,
                    start=start,
                    end=end,
                    app_names=app_name_list,
                )
                if use_facet
                else {}
            )

        # Convert Entity list to SearchHit list
        hits = []
        for entity in entities:
            entity_search_result = EntitySearchResult(
                id=str(entity.id),
                filepath=entity.filepath,
                filename=entity.filename,
                size=entity.size,
                file_created_at=entity.file_created_at,
                file_last_modified_at=entity.file_last_modified_at,
                file_type=entity.file_type,
                file_type_group=entity.file_type_group,
                last_scan_at=entity.last_scan_at if entity.last_scan_at else None,
                library_id=entity.library_id,
                folder_id=entity.folder_id,
                tags=[tag.name for tag in entity.tags],
                metadata_entries=[
                    MetadataIndexItem(
                        key=metadata.key,
                        value=(
                            json.loads(metadata.value)
                            if metadata.data_type == MetadataType.JSON_DATA
                            else metadata.value
                        ),
                        source=metadata.source,
                    )
                    for metadata in entity.metadata_entries
                ],
            )

            hits.append(
                SearchHit(
                    document=entity_search_result,
                    highlight={},
                    highlights=[],
                    text_match=None,
                    hybrid_search_info=None,
                    text_match_info=None,
                )
            )

        # Convert tag_counts to facet_counts format
        app_name_facet_counts = []
        if stats and "app_name_counts" in stats:
            for app_name, count in stats["app_name_counts"].items():
                app_name_facet_counts.append(
                    FacetCount(
                        value=app_name,
                        count=count,
                        highlighted=app_name,
                    )
                )

        facet_counts = (
            [
                Facet(
                    field_name="app_names",
                    counts=app_name_facet_counts,
                    sampled=False,
                    stats=FacetStats(total_values=len(app_name_facet_counts)),
                )
            ]
            if app_name_facet_counts
            else []
        )

        # Build SearchResult
        search_result = SearchResult(
            facet_counts=facet_counts,
            found=len(hits),
            hits=hits,
            out_of=len(hits),
            page=1,
            request_params=RequestParams(
                collection_name="entities",
                first_q=q,
                per_page=limit,
                q=q,
                app_names=app_name_list,
            ),
            search_cutoff=False,
            search_time_ms=0,
        )

        return search_result

    except Exception as e:
        logging.error("Error searching entities: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

@api_router.get(
    "/libraries/{library_id}/entities/{entity_id}/context",
    response_model=EntityContext,
    tags=["entity"],
)
def get_entity_context(
    library_id: int,
    entity_id: int,
    prev: Annotated[int | None, Query(ge=0, le=100)] = None,
    next: Annotated[int | None, Query(ge=0, le=100)] = None,
    db: Session = Depends(get_db),
):
    """
    Get the context (previous and next entities) for a given entity.

    Args:
        library_id: The ID of the library
        entity_id: The ID of the target entity
        prev: Number of previous entities to fetch (optional)
        next: Number of next entities to fetch (optional)

    Returns:
        EntityContext object containing prev and next lists of entities
    """
    # If both prev and next are None, return empty lists
    if prev is None and next is None:
        return EntityContext(prev=[], next=[])

    # Convert None to 0 for the crud function
    prev_count = prev if prev is not None else 0
    next_count = next if next is not None else 0

    # Get the context entities
    prev_entities, next_entities = crud.get_entity_context(
        db=db,
        library_id=library_id,
        entity_id=entity_id,
        prev=prev_count,
        next=next_count,
    )

    # Return the context object
    return EntityContext(prev=prev_entities, next=next_entities)

@api_router.get("/config", tags=["config"])
async def get_config():
    """Get the current configuration"""
    config = load_config()
    # Convert to dict and handle SecretStr fields
    config_dict = config.model_dump()
    
    # Format SecretStr fields as masked values
    for section_name, section in config_dict.items():
        if isinstance(section, dict):
            for key, value in section.items():
                if hasattr(value, "get_secret_value"):
                    section[key] = "********"
    
    return config_dict

@api_router.put("/config", tags=["config"])
async def update_config(config_updates: dict):
    """Update the configuration"""
    try:
        # Load current config
        current_config = load_config()
        current_dict = current_config.model_dump()
        
        # Track which components need restart
        needs_restart = {"serve": False, "watch": False, "record": False}
        
        # Apply updates
        updated_config, restart_info = apply_config_updates(current_dict, config_updates)
        
        # Update needs_restart based on changes
        for component, required in restart_info.items():
            if required:
                needs_restart[component] = True
        
        # Save the updated config
        save_config(updated_config)
        
        # Handle restarts
        restart_processes(needs_restart)
        
        return {"success": True, "restart_required": needs_restart}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update config: {str(e)}")

@api_router.post("/config/restart", tags=["config"])
async def restart_services(components: dict = {"serve": True, "watch": True, "record": True}):
    """Restart specified components"""
    from memos.service_manager import api_restart_services
    
    results = api_restart_services(components)
    has_serve = components.get("serve", False)
    
    return {
        "success": True, 
        "message": "Restart operation scheduled" if has_serve else "Restart completed",
        "results": {k: "Scheduled" if v else "Failed" for k, v in results.items()}
    }

def run_server():
    # Clean up old thumbnails on startup
    cleanup_thumbnails()

    # Schedule periodic thumbnail cleanup
    schedule_thumbnail_cleanup()

    logging.info("Database path: %s", settings.database_url)
    logging.info("VLM plugin enabled: %s", settings.vlm.enabled)
    logging.info("OCR plugin enabled: %s", settings.ocr.enabled)

    # Only add VLM plugin router if enabled
    if settings.vlm.enabled:
        vlm_main.init_plugin(settings.vlm)
        api_router.include_router(vlm_main.router, prefix="/plugins/vlm")
        logging.info("VLM plugin initialized and router added")
    else:
        logging.info("VLM plugin disabled")

    # Only add OCR plugin router if enabled
    if settings.ocr.enabled:
        ocr_main.init_plugin(settings.ocr)
        api_router.include_router(ocr_main.router, prefix="/plugins/ocr")
        logging.info("OCR plugin initialized and router added")
    else:
        logging.info("OCR plugin disabled")

    uvicorn.run(
        "memos.server:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
        log_config=LOGGING_CONFIG,
    )
