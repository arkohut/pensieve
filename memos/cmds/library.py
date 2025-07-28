# Standard library imports
import time
import math
import re
import os
import threading
import asyncio
import logging
import logging.config
from pathlib import Path
from datetime import datetime, timezone
from enum import Enum
from typing import List, Tuple, Dict, Any, Optional, Set
from functools import lru_cache
from collections import defaultdict, deque

# Third-party imports
import typer
import httpx
from tqdm import tqdm
from tabulate import tabulate
import psutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from concurrent.futures import ThreadPoolExecutor

# Local imports
from memos.config import settings
from memos.utils import get_image_metadata
from memos.schemas import MetadataSource
from memos.logging_config import LOGGING_CONFIG
from memos.record import is_app_blacklisted, get_active_window_info


logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

lib_app = typer.Typer()

file_detector = None

IS_THUMBNAIL = "is_thumbnail"

BASE_URL = settings.server_endpoint

include_files = [".jpg", ".jpeg", ".png", ".webp"]


class FileStatus(Enum):
    UPDATED = "updated"
    ADDED = "added"


def format_timestamp(timestamp):
    if isinstance(timestamp, str):
        return timestamp
    return (
        datetime.fromtimestamp(timestamp, tz=timezone.utc)
        .replace(tzinfo=None)
        .isoformat()
    )


def init_file_detector():
    """Initialize the global file detector if not already initialized"""
    global file_detector
    if file_detector is None:
        from magika import Magika

        file_detector = Magika()
    return file_detector


def get_file_type(file_path):
    """Get file type using lazy-loaded detector"""
    detector = init_file_detector()
    file_result = detector.identify_path(file_path)
    return file_result.output.ct_label, file_result.output.group


def display_libraries(libraries):
    table = []
    for library in libraries:
        table.append(
            [
                library["id"],
                library["name"],
                "\n".join(
                    f"{folder['id']}: {folder['path']}" for folder in library["folders"]
                ),
                "\n".join(
                    f"{plugin['id']}: {plugin['name']} {plugin['webhook_url']}"
                    for plugin in library["plugins"]
                ),
            ]
        )

    print(
        tabulate(table, headers=["ID", "Name", "Folders", "Plugins"], tablefmt="plain")
    )


@lib_app.command("ls")
def ls():
    response = httpx.get(f"{BASE_URL}/api/libraries")
    libraries = response.json()
    display_libraries(libraries)


@lib_app.command("create")
def add(name: str, folders: List[str]):
    absolute_folders = []
    for folder in folders:
        folder_path = Path(folder).resolve()
        absolute_folders.append(
            {
                "path": str(folder_path),
                "last_modified_at": datetime.fromtimestamp(
                    folder_path.stat().st_mtime
                ).isoformat(),
            }
        )

    response = httpx.post(
        f"{BASE_URL}/api/libraries", json={"name": name, "folders": absolute_folders}
    )
    if 200 <= response.status_code < 300:
        print("Library created successfully")
    else:
        print(f"Failed to create library: {response.status_code} - {response.text}")


@lib_app.command("add-folder")
def add_folder(library_id: int, folders: List[str]):
    absolute_folders = []
    for folder in folders:
        folder_path = Path(folder).resolve()
        absolute_folders.append(
            {
                "path": str(folder_path),
                "last_modified_at": datetime.fromtimestamp(
                    folder_path.stat().st_mtime
                ).isoformat(),
            }
        )

    response = httpx.post(
        f"{BASE_URL}/api/libraries/{library_id}/folders",
        json={"folders": absolute_folders},
    )
    if 200 <= response.status_code < 300:
        print("Folders added successfully")
        library = response.json()
        display_libraries([library])
    else:
        print(f"Failed to add folders: {response.status_code} - {response.text}")


@lib_app.command("show")
def show(library_id: int):
    response = httpx.get(f"{BASE_URL}/api/libraries/{library_id}")
    if response.status_code == 200:
        library = response.json()
        display_libraries([library])
    else:
        print(f"Failed to retrieve library: {response.status_code} - {response.text}")


def is_temp_file(filename):
    return (
        filename.startswith(".")
        or filename.startswith("tmp")
        or filename.startswith("temp")
    )


async def loop_files(library, folder, folder_path, force, plugins, batch_size):
    """
    Process files in the folder

    Args:
        library: Library object
        folder: Folder information
        folder_path: Folder path
        force: Whether to force update
        plugins: List of plugins
        batch_size: Batch size

    Returns:
        Tuple[int, int, int]: (Number of files added, Number of files updated, Number of files deleted)
    """
    updated_file_count = 0
    added_file_count = 0
    deleted_file_count = 0
    semaphore = asyncio.Semaphore(batch_size)

    async with httpx.AsyncClient(timeout=300) as client:
        # 1. Collect candidate files
        candidate_files = await collect_candidate_files(folder_path)
        scanned_files = set(candidate_files)

        # 2. Process file batches
        added_file_count, updated_file_count = await process_file_batches(
            client,
            library,
            folder,
            candidate_files,
            force,
            plugins,
            semaphore,
        )

        # 3. Check for deleted files
        deleted_file_count = await check_deleted_files(
            client, library.get("id"), folder, folder_path, scanned_files
        )

        return added_file_count, updated_file_count, deleted_file_count


@lib_app.command("scan")
def scan(
    library_id: int,
    path: str = typer.Argument(None, help="Path to scan within the library"),
    force: bool = False,
    plugins: List[int] = typer.Option(None, "--plugin", "-p"),
    folders: List[int] = typer.Option(None, "--folder", "-f"),
    batch_size: int = typer.Option(
        1, "--batch-size", "-bs", help="Batch size for processing files"
    ),
):
    # Check if both path and folders are provided
    if path and folders:
        print("Error: You cannot specify both a path and folders at the same time.")
        return

    response = httpx.get(f"{BASE_URL}/api/libraries/{library_id}")
    if response.status_code != 200:
        print(f"Failed to retrieve library: {response.status_code} - {response.text}")
        return

    library = response.json()
    total_files_added = 0
    total_files_updated = 0
    total_files_deleted = 0

    # Filter folders if the folders parameter is provided
    if folders:
        library_folders = [
            folder for folder in library["folders"] if folder["id"] in folders
        ]
    else:
        library_folders = library["folders"]

    # Check if a specific path is provided
    if path:
        path = Path(path).expanduser().resolve()
        # Check if the path is a folder or a subdirectory of a library folder
        folder = next(
            (
                folder
                for folder in library_folders
                if path.is_relative_to(Path(folder["path"]).resolve())
            ),
            None,
        )
        if not folder:
            print(f"Error: The path {path} is not part of any folder in the library.")
            return
        # Only scan the specified path
        library_folders = [{"id": folder["id"], "path": str(path)}]

    for folder in library_folders:
        folder_path = Path(folder["path"])
        if not folder_path.exists() or not folder_path.is_dir():
            tqdm.write(f"Folder does not exist or is not a directory: {folder_path}")
            continue

        added_file_count, updated_file_count, deleted_file_count = asyncio.run(
            loop_files(library, folder, folder_path, force, plugins, batch_size)
        )
        total_files_added += added_file_count
        total_files_updated += updated_file_count
        total_files_deleted += deleted_file_count

    print(f"Total files added: {total_files_added}")
    print(f"Total files updated: {total_files_updated}")
    print(f"Total files deleted: {total_files_deleted}")


async def add_entity(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    library_id,
    plugins,
    new_entity,
) -> Tuple[FileStatus, bool, httpx.Response]:
    async with semaphore:
        MAX_RETRIES = 3
        RETRY_DELAY = 2.0
        for attempt in range(MAX_RETRIES):
            try:
                post_response = await client.post(
                    f"{BASE_URL}/api/libraries/{library_id}/entities",
                    json=new_entity,
                    params=(
                        {"plugins": plugins, "update_index": "true"}
                        if plugins
                        else {"update_index": "true"}
                    ),
                    timeout=300,
                )
                if 200 <= post_response.status_code < 300:
                    return new_entity["filepath"], FileStatus.ADDED, True, post_response
                else:
                    return (
                        new_entity["filepath"],
                        FileStatus.ADDED,
                        False,
                        post_response,
                    )
            except Exception as e:
                logging.error(
                    f"Error while adding entity (attempt {attempt + 1}/{MAX_RETRIES}): {e}"
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    return new_entity["filepath"], FileStatus.ADDED, False, None


async def update_entity(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    plugins,
    new_entity,
    existing_entity,
    force: bool = False,
) -> Tuple[FileStatus, bool, httpx.Response]:
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0
    async with semaphore:
        for attempt in range(MAX_RETRIES):
            try:
                update_response = await client.put(
                    f"{BASE_URL}/api/entities/{existing_entity['id']}",
                    json=new_entity,
                    params={
                        "trigger_webhooks_flag": "true",
                        "update_index": "true",
                        "force": str(force).lower(),
                        **({"plugins": plugins} if plugins else {}),
                    },
                    timeout=300,
                )
                if 200 <= update_response.status_code < 300:
                    return (
                        new_entity["filepath"],
                        FileStatus.UPDATED,
                        True,
                        update_response,
                    )
                else:
                    return (
                        new_entity["filepath"],
                        FileStatus.UPDATED,
                        False,
                        update_response,
                    )
            except Exception as e:
                logging.error(
                    f"Error while updating entity {existing_entity['id']} (attempt {attempt + 1}/{MAX_RETRIES}): {e}"
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    return new_entity["filepath"], FileStatus.UPDATED, False, None


@lib_app.command("reindex")
def reindex(
    library_id: int,
    folders: List[int] = typer.Option(None, "--folder", "-f"),
    force: bool = typer.Option(
        False, "--force", help="Force recreate FTS and vector tables before reindexing"
    ),
    batch_size: int = typer.Option(
        1, "--batch-size", "-bs", help="Batch size for processing entities"
    ),
):
    print(f"Reindexing library {library_id}")

    from memos.databases.initializers import recreate_fts_and_vec_tables

    # Get the library
    response = httpx.get(f"{BASE_URL}/api/libraries/{library_id}")
    if response.status_code != 200:
        print(f"Failed to get library: {response.status_code} - {response.text}")
        return

    library = response.json()
    scanned_entities = set()

    # Filter folders if the folders parameter is provided
    if folders:
        library_folders = [
            folder for folder in library["folders"] if folder["id"] in folders
        ]
    else:
        library_folders = library["folders"]

    if force:
        print("Force flag is set. Recreating FTS and vector tables...")
        if not recreate_fts_and_vec_tables(settings):
            return
        print("FTS and vector tables have been recreated.")

    with httpx.Client() as client:
        total_entities = 0

        # Get total entity count for all folders
        for folder in library_folders:
            response = client.get(
                f"{BASE_URL}/api/libraries/{library_id}/folders/{folder['id']}/entities",
                params={"limit": 1, "offset": 0},
            )
            if response.status_code == 200:
                total_entities += int(response.headers.get("X-Total-Count", 0))
            else:
                print(
                    f"Failed to get entity count for folder {folder['id']}: {response.status_code} - {response.text}"
                )

        # Now process entities with a progress bar
        with tqdm(total=total_entities, desc="Reindexing entities") as pbar:
            for folder in library_folders:
                print(f"Processing folder: {folder['id']}")

                # List all entities in the folder
                limit = 200
                offset = 0
                while True:
                    entities_response = client.get(
                        f"{BASE_URL}/api/libraries/{library_id}/folders/{folder['id']}/entities",
                        params={"limit": limit, "offset": offset},
                    )
                    if entities_response.status_code != 200:
                        print(
                            f"Failed to get entities: {entities_response.status_code} - {entities_response.text}"
                        )
                        break

                    entities = entities_response.json()
                    if not entities:
                        break

                    # Collect entity IDs to be processed
                    entity_ids = [
                        entity["id"]
                        for entity in entities
                        if entity["id"] not in scanned_entities
                    ]

                    # Process in batches
                    for i in range(0, len(entity_ids), batch_size):
                        batch_ids = entity_ids[i : i + batch_size]
                        if batch_ids:
                            batch_response = client.post(
                                f"{BASE_URL}/api/entities/batch-index",
                                json={"entity_ids": batch_ids},
                                timeout=300,
                            )
                            if batch_response.status_code != 204:
                                print(
                                    f"Failed to update batch: {batch_response.status_code} - {batch_response.text}"
                                )
                            pbar.update(len(batch_ids))
                            scanned_entities.update(batch_ids)

                    offset += limit

    if folders:
        print(f"Reindexing completed for library {library_id} with folders: {folders}")
    else:
        print(f"Reindexing completed for library {library_id}")


def has_entity_changes(new_entity: dict, existing_entity: dict) -> bool:
    """
    Compare new_entity with existing_entity to determine if there are actual changes.
    Returns True if there are differences, False otherwise.
    """
    # Compare basic fields
    basic_fields = [
        "filename",
        "filepath",
        "size",
        "file_created_at",
        "file_last_modified_at",
        "file_type",
        "file_type_group",
    ]

    for field in basic_fields:
        if new_entity.get(field) != existing_entity.get(field):
            return True

    # Compare metadata entries
    new_metadata = {
        (entry["key"], entry["value"])
        for entry in new_entity.get("metadata_entries", [])
    }
    existing_metadata = {
        (entry["key"], entry["value"])
        for entry in existing_entity.get("metadata_entries", [])
    }
    if new_metadata != existing_metadata:
        return True

    # Compare tags
    new_tags = set(new_entity.get("tags", []))
    existing_tags = {tag["name"] for tag in existing_entity.get("tags", [])}
    if new_tags != existing_tags:
        return True

    return False


@lib_app.command("sync")
def sync(
    library_id: int,
    filepath: str,
    force: bool = typer.Option(
        False, "--force", "-f", help="Force update the file and reprocess with plugins"
    ),
    without_webhooks: bool = typer.Option(
        False, "--no-plugins", help="Disable plugin triggers", is_flag=True
    ),
):
    """
    Sync a specific file with the library.
    """
    # 1. Get library by id and check if it exists
    response = httpx.get(f"{BASE_URL}/api/libraries/{library_id}")
    if response.status_code != 200:
        typer.echo(f"Error: Library with id {library_id} not found.")
        raise typer.Exit(code=1)

    library = response.json()

    # Convert filepath to absolute path
    file_path = Path(filepath).resolve()

    if not file_path.is_file():
        typer.echo(f"Error: File {file_path} does not exist.")
        raise typer.Exit(code=1)

    # 2. Check if the file exists in the library
    response = httpx.get(
        f"{BASE_URL}/api/libraries/{library_id}/entities/by-filepath",
        params={"filepath": str(file_path)},
    )

    file_stat = file_path.stat()
    file_type, file_type_group = get_file_type(file_path)

    # 比较st_mtime和st_ctime，使用较早的时间作为file_created_at
    created_at_timestamp = file_stat.st_ctime
    if file_stat.st_mtime < file_stat.st_ctime:
        created_at_timestamp = file_stat.st_mtime

    new_entity = {
        "filename": file_path.name,
        "filepath": str(file_path),
        "size": file_stat.st_size,
        "file_created_at": format_timestamp(created_at_timestamp),
        "file_last_modified_at": format_timestamp(file_stat.st_mtime),
        "file_type": file_type,
        "file_type_group": file_type_group,
    }

    # Handle image metadata
    is_thumbnail = False
    metadata_timestamp = None  # Default: no timestamp from metadata
    if file_type_group == "image":
        metadata = get_image_metadata(file_path)
        if metadata:
            # Use parse_timestamp_from_metadata to get the timestamp
            metadata_timestamp = parse_timestamp_from_metadata(metadata)
            if "active_window" in metadata and "active_app" not in metadata:
                metadata["active_app"] = metadata["active_window"].split(" - ")[0]
            new_entity["metadata_entries"] = [
                {
                    "key": key,
                    "value": str(value),
                    "source": MetadataSource.SYSTEM_GENERATED.value,
                    "data_type": (
                        "number" if isinstance(value, (int, float)) else "text"
                    ),
                }
                for key, value in metadata.items()
                if key != IS_THUMBNAIL
            ]
            if "active_app" in metadata:
                new_entity.setdefault("tags", []).append(metadata["active_app"])
            is_thumbnail = metadata.get(IS_THUMBNAIL, False)

            if is_thumbnail:
                typer.echo(f"Skipping thumbnail file: {file_path}")
                return

    # If metadata_timestamp is set, use it for file_created_at
    if metadata_timestamp is not None:
        new_entity["file_created_at"] = format_timestamp(metadata_timestamp)

    if response.status_code == 200:
        # File exists, update it
        existing_entity = response.json()
        new_entity["folder_id"] = existing_entity["folder_id"]

        if is_thumbnail:
            new_entity["file_created_at"] = existing_entity["file_created_at"]
            new_entity["file_last_modified_at"] = existing_entity[
                "file_last_modified_at"
            ]
            new_entity["file_type"] = existing_entity["file_type"]
            new_entity["file_type_group"] = existing_entity["file_type_group"]
            new_entity["size"] = existing_entity["size"]

        if not force:
            # When not forcing, preserve existing metadata
            new_metadata_keys = {
                entry["key"] for entry in new_entity.get("metadata_entries", [])
            }
            for existing_entry in existing_entity.get("metadata_entries", []):
                if existing_entry["key"] not in new_metadata_keys:
                    new_entity.setdefault("metadata_entries", []).append(existing_entry)

            # Merge existing tags with new tags
            existing_tags = {tag["name"] for tag in existing_entity.get("tags", [])}
            new_tags = set(new_entity.get("tags", []))
            merged_tags = new_tags.union(existing_tags)
            new_entity["tags"] = list(merged_tags)

        # Only update if there are actual changes or force flag is set
        has_changes = has_entity_changes(new_entity, existing_entity)
        
        if force or has_changes:
            # When forcing, always trigger webhooks unless explicitly disabled
            should_trigger_webhooks = not without_webhooks if not force else True
            
            update_response = httpx.put(
                f"{BASE_URL}/api/entities/{existing_entity['id']}",
                json=new_entity,
                params={
                    "trigger_webhooks_flag": str(should_trigger_webhooks).lower(),
                    "update_index": "true",
                    "force": str(force).lower(),
                },
                timeout=300,
            )
            if update_response.status_code == 200:
                if force:
                    typer.echo(f"Updated file and scheduled for plugin reprocessing: {file_path}")
                else:
                    typer.echo(f"Updated file: {file_path}")
            else:
                typer.echo(
                    f"Error updating file: {update_response.status_code} - {update_response.text}"
                )
        elif not without_webhooks:
            # Send update request with trigger_webhooks_flag=true 
            # The server-side trigger_webhooks function will only process plugins 
            # that haven't processed this entity yet
            update_response = httpx.put(
                f"{BASE_URL}/api/entities/{existing_entity['id']}",
                json=new_entity,
                params={
                    "trigger_webhooks_flag": "true",
                    "update_index": "true",
                    "force": "false",
                },
                timeout=300,
            )
            if update_response.status_code == 200:
                # Assume plugins may have been processed, since server-side will process any pending plugins
                typer.echo(f"File content unchanged, checking for pending plugins: {file_path}")
            else:
                typer.echo(
                    f"Error updating file: {update_response.status_code} - {update_response.text}"
                )
        else:
            typer.echo(f"File {file_path} is up to date. No changes detected.")
    else:
        # 3. File doesn't exist, check if it belongs to a folder in the library
        folder = next(
            (
                folder
                for folder in library["folders"]
                if str(file_path).startswith(folder["path"])
            ),
            None,
        )

        if folder:
            # Create new entity
            new_entity["folder_id"] = folder["id"]

            create_response = httpx.post(
                f"{BASE_URL}/api/libraries/{library_id}/entities",
                json=new_entity,
                params={
                    "trigger_webhooks_flag": str(not without_webhooks).lower(),
                    "update_index": "true",
                },
                timeout=300,
            )

            if create_response.status_code == 200:
                typer.echo(f"Created new entity for file: {file_path}")
            else:
                typer.echo(
                    f"Error creating entity: {create_response.status_code} - {create_response.text}"
                )

        else:
            # 4. File doesn't belong to any folder in the library
            typer.echo(
                f"Error: File {file_path} does not belong to any folder in the library."
            )
            raise typer.Exit(code=1)


@lru_cache(maxsize=1)
def is_on_battery():
    try:
        battery = psutil.sensors_battery()
        return battery is not None and not battery.power_plugged
    except:
        return False  # If unable to detect battery status, assume not on battery


class LibraryFileHandler(FileSystemEventHandler):
    # Constants for file tracking
    MAX_RETRIES = 3
    BATTERY_CHECK_INTERVAL = 60  # seconds
    BUFFER_TIME = 2  # seconds

    def __init__(
        self,
        library_id,
        include_files,
        max_workers=2,
        sparsity_factor=3,
        rate_window_size=10,
        processing_interval=12,
    ):
        self.library_id = library_id
        self.include_files = include_files
        self.inode_pattern = re.compile(r"\._.+")
        self.pending_files = defaultdict(lambda: {"timestamp": 0, "last_size": 0})
        self.buffer_time = self.BUFFER_TIME
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.lock = threading.Lock()

        self.processing_interval = processing_interval
        self.sparsity_factor = sparsity_factor
        self.rate_window_size = rate_window_size

        self.file_change_intervals = deque(maxlen=rate_window_size)
        self.file_processing_durations = deque(maxlen=rate_window_size)

        # Counters for real-time file processing
        self.file_count = 0
        self.file_submitted = 0
        self.file_synced = 0
        self.file_skipped = 0

        # Counter for background processing during idle time
        self.background_synced = 0

        self.logger = logger

        self.last_battery_check = 0
        self.battery_check_interval = self.BATTERY_CHECK_INTERVAL

        # State tracking
        self.state = "busy"
        self.last_activity_time = time.time()
        self.idle_timeout = settings.watch.idle_timeout
        self.idle_process_start = datetime.strptime(
            settings.watch.idle_process_interval[0], "%H:%M"
        ).time()
        self.idle_process_end = datetime.strptime(
            settings.watch.idle_process_interval[1], "%H:%M"
        ).time()

        # Track retry attempts for failed files
        self.failed_retries = defaultdict(int)
        self.max_retries = self.MAX_RETRIES
        self.is_processing_skipped = False

        # Track the last processing window state
        self.last_in_process_window = self.is_within_process_interval()

    def is_within_process_interval(self) -> bool:
        """Check if current time is within the idle process interval"""
        current_time = datetime.now().time()

        # If end time is less than start time, it means the interval crosses midnight
        if self.idle_process_end < self.idle_process_start:
            return (
                current_time >= self.idle_process_start
                or current_time <= self.idle_process_end
            )

        return self.idle_process_start <= current_time <= self.idle_process_end

    def handle_event(self, event):
        app_name, _, _ = get_active_window_info()
        if is_app_blacklisted(app_name):
            self.logger.info(f"App '{app_name}' is blacklisted. Ignoring file event for {event.src_path}", 
                             extra={"log_type": "bg"})
            return False
            
        if not event.is_directory and self.is_valid_file(event.src_path):
            current_time = time.time()
            with self.lock:
                file_info = self.pending_files[event.src_path]
                self.last_activity_time = current_time
                self.state = "busy"
                # Stop processing skipped files when new files come in
                self.is_processing_skipped = False

                if current_time - file_info["timestamp"] > self.buffer_time:
                    file_info["timestamp"] = current_time
                    self.file_change_intervals.append(current_time)

                file_info["last_size"] = os.path.getsize(event.src_path)

            return True
        return False

    def check_state(self):
        """Check and update the current state based on activity"""
        current_time = time.time()
        with self.lock:
            is_idle = (current_time - self.last_activity_time) > self.idle_timeout
            current_in_process_window = self.is_within_process_interval()

            # Check if we've entered a new processing window
            window_state_changed = (
                current_in_process_window != self.last_in_process_window
            )
            self.last_in_process_window = current_in_process_window

            if is_idle:
                if self.state != "idle":
                    self.state = "idle"
                    self.logger.info(
                        f"State changed to idle (no activity for {self.idle_timeout} seconds)",
                        extra={"log_type": "bg"}
                    )
                    # Start processing unprocessed files when entering idle state
                    if not is_on_battery() and current_in_process_window:
                        self.process_unprocessed_files()
                    else:
                        reasons = []
                        if is_on_battery():
                            reasons.append("on battery")
                        if not current_in_process_window:
                            reasons.append(
                                f"outside processing hours {settings.watch.idle_process_interval[0]}-{settings.watch.idle_process_interval[1]}"
                            )
                        self.logger.info(
                            f"Not processing unprocessed files ({', '.join(reasons)})",
                            extra={"log_type": "bg"}
                        )
                elif (
                    window_state_changed
                    and current_in_process_window
                    and not is_on_battery()
                ):
                    # We're already idle and just entered the processing window
                    self.logger.info(
                        "Entered processing window while idle, starting to process files",
                        extra={"log_type": "bg"}
                    )
                    self.process_unprocessed_files()
            else:
                if self.state != "busy":
                    self.state = "busy"
                    self.logger.info("State changed to busy", extra={"log_type": "bg"})

    def process_unprocessed_files(self):
        """Process unprocessed files using the API endpoint"""
        if self.is_processing_skipped:
            return

        if is_on_battery():
            self.logger.info("Not processing unprocessed files while on battery", extra={"log_type": "bg"})
            return

        if not self.is_within_process_interval():
            self.logger.info(
                f"Not processing unprocessed files outside of hours {settings.watch.idle_process_interval[0]}-{settings.watch.idle_process_interval[1]}",
                extra={"log_type": "bg"}
            )
            return

        self.is_processing_skipped = True
        self.logger.info("Starting background processing", extra={
            "event": "background_processing_start",
            "idle_timeout": self.idle_timeout,
            "process_interval": f"{settings.watch.idle_process_interval[0]}-{settings.watch.idle_process_interval[1]}",
            "log_type": "bg"
        })

        def process_files():
            while True:
                # Check state conditions at the start of each iteration
                if not self.is_processing_skipped:
                    self.logger.info("Background processing stopped: processing_skipped flag cleared", 
                                   extra={"log_type": "bg"})
                    break

                if is_on_battery():
                    self.logger.info("Background processing stopped: system on battery", 
                                   extra={"log_type": "bg"})
                    self.is_processing_skipped = False
                    break

                if not self.is_within_process_interval():
                    self.logger.info(
                        f"Background processing stopped: outside processing hours {settings.watch.idle_process_interval[0]}-{settings.watch.idle_process_interval[1]}", 
                        extra={"log_type": "bg"}
                    )
                    self.is_processing_skipped = False
                    break

                if self.state != "idle":
                    self.logger.info("Background processing stopped: system no longer idle", 
                                   extra={"log_type": "bg"})
                    self.is_processing_skipped = False
                    break

                try:
                    # Get library information to get folder IDs
                    library_response = httpx.get(
                        f"{BASE_URL}/api/libraries/{self.library_id}"
                    )
                    library_response.raise_for_status()
                    library = library_response.json()

                    has_unprocessed_files = False
                    cycle_stats = {
                        "processed_count": 0,
                        "failed_count": 0,
                        "skipped_count": 0
                    }

                    # Process each folder
                    for folder in library["folders"]:
                        self.logger.debug("Processing folder", extra={
                            "event": "folder_processing_start",
                            "folder_id": folder['id'],
                            "library_id": self.library_id,
                            "log_type": "bg"
                        })

                        # Get unprocessed files from API for this folder
                        response = httpx.get(
                            f"{BASE_URL}/api/libraries/{self.library_id}/folders/{folder['id']}/entities",
                            params={"limit": 10, "unprocessed_only": True},
                        )
                        response.raise_for_status()
                        entities = response.json()

                        if not entities:
                            self.logger.debug("No unprocessed files found in folder", extra={
                                "event": "folder_processing_empty",
                                "folder_id": folder['id'],
                                "log_type": "bg"
                            })
                            continue

                        has_unprocessed_files = True
                        for entity in entities:
                            # Re-check conditions before processing each entity
                            if not self.is_processing_skipped or is_on_battery() or not self.is_within_process_interval() or self.state != "idle":
                                return

                            filepath = entity["filepath"]
                            if not os.path.exists(filepath):
                                self.logger.debug("File not found, skipping", extra={
                                    "event": "entity_processing_skip",
                                    "entity_id": entity['id'],
                                    "filepath": filepath,
                                    "reason": "file_not_found",
                                    "log_type": "bg"
                                })
                                cycle_stats["skipped_count"] += 1
                                continue

                            self.logger.debug("Processing file", extra={
                                "event": "entity_processing_start",
                                "entity_id": entity['id'],
                                "filepath": filepath,
                                "log_type": "bg"
                            })

                            try:
                                sync(self.library_id, filepath, without_webhooks=False, force=False)
                                with self.lock:
                                    self.background_synced += 1
                                    self.failed_retries.pop(filepath, None)
                                cycle_stats["processed_count"] += 1
                                
                                self.logger.debug("Successfully processed file", extra={
                                    "event": "entity_processing_success",
                                    "entity_id": entity['id'],
                                    "filepath": filepath,
                                    "log_type": "bg"
                                })
                            except Exception as e:
                                cycle_stats["failed_count"] += 1
                                with self.lock:
                                    retry_count = self.failed_retries[filepath] + 1
                                    if retry_count < self.max_retries:
                                        self.failed_retries[filepath] = retry_count
                                        self.logger.info(
                                            f"Will retry file {filepath} (attempt {retry_count}/{self.max_retries})",
                                            extra={
                                                "event": "entity_processing_retry",
                                                "entity_id": entity['id'],
                                                "filepath": filepath,
                                                "retry_count": retry_count,
                                                "max_retries": self.max_retries,
                                                "error": str(e),
                                                "log_type": "bg"
                                            }
                                        )
                                    else:
                                        self.logger.warning(
                                            f"Giving up on file {filepath} after {self.max_retries} attempts",
                                            extra={
                                                "event": "entity_processing_give_up",
                                                "entity_id": entity['id'],
                                                "filepath": filepath,
                                                "max_retries": self.max_retries,
                                                "error": str(e),
                                                "log_type": "bg"
                                            }
                                        )
                                        self.failed_retries.pop(filepath, None)

                    # Log cycle summary
                    if cycle_stats["processed_count"] > 0 or cycle_stats["failed_count"] > 0:
                        self.logger.info("Background processing cycle completed", extra={
                            "event": "background_processing_cycle_complete",
                            "processed_count": cycle_stats["processed_count"],
                            "failed_count": cycle_stats["failed_count"],
                            "skipped_count": cycle_stats["skipped_count"],
                            "has_unprocessed_files": has_unprocessed_files,
                            "log_type": "bg"
                        })

                    # If we've gone through all folders and found no files to process, wait before starting over
                    if not has_unprocessed_files:
                        self.logger.debug("No unprocessed files found in any folder, waiting before next cycle", extra={
                            "event": "background_processing_wait",
                            "wait_time": 60,
                            "log_type": "bg"
                        })
                        time.sleep(60)

                except Exception as e:
                    self.logger.error("Error in background processing", extra={
                        "event": "background_processing_error",
                        "error": str(e),
                        "log_type": "bg"
                    })
                    self.is_processing_skipped = False
                    return

        # Start processing in a separate thread
        self.executor.submit(process_files)

    def process_pending_files(self):
        current_time = time.time()
        files_to_process_with_plugins = []
        files_to_process_without_plugins = []
        processed_in_current_loop = 0
        with self.lock:
            for path, file_info in list(self.pending_files.items()):
                if current_time - file_info["timestamp"] <= self.buffer_time:
                    continue

                processed_in_current_loop += 1

                if os.path.exists(path) and os.path.getsize(path) > 0:
                    self.file_count += 1
                    if self.file_count % self.processing_interval == 0:
                        files_to_process_with_plugins.append(path)
                        print(
                            f"file_count % processing_interval: {self.file_count} % {self.processing_interval} == 0"
                        )
                        print(f"Picked file for processing with plugins: {path}")
                    else:
                        files_to_process_without_plugins.append(path)
                        self.file_skipped += 1
                del self.pending_files[path]

        # Process files with plugins - these count as submitted
        for path in files_to_process_with_plugins:
            self.executor.submit(self.process_file, path, False)
            self.file_submitted += 1

        # Process files without plugins - these don't count as submitted
        for path in files_to_process_without_plugins:
            self.executor.submit(self.process_file, path, True)

        if processed_in_current_loop > 0:
            self.logger.info(
                f"Real-time stats - "
                f"File count: {self.file_count}, "
                f"Files submitted: {self.file_submitted}, "
                f"Files synced: {self.file_synced}, "
                f"Files skipped: {self.file_skipped}, "
                f"Failed retries: {len(self.failed_retries)}, "
                f"Current state: {self.state}",
                extra={"log_type": "bg"}
            )
            if self.background_synced > 0:
                self.logger.info(
                    f"Background processing - Files synced: {self.background_synced}",
                    extra={"log_type": "bg"}
                )

        self.check_state()
        self.update_processing_interval()

    def process_file(self, path, no_plugins):
        self.logger.debug(f"Processing file: {path} (with plugins: {not no_plugins})")
        start_time = time.time()
        sync(self.library_id, path, without_webhooks=no_plugins, force=False)
        end_time = time.time()
        if not no_plugins:
            with self.lock:
                self.file_processing_durations.append(end_time - start_time)
                self.file_synced += 1

    def update_processing_interval(self):
        min_samples = max(3, self.rate_window_size // 3)
        max_interval = 60  # Maximum allowed interval between events in seconds

        if (
            len(self.file_change_intervals) >= min_samples
            and len(self.file_processing_durations) >= min_samples
        ):
            # Filter out large time gaps
            filtered_intervals = [
                self.file_change_intervals[i] - self.file_change_intervals[i - 1]
                for i in range(1, len(self.file_change_intervals))
                if self.file_change_intervals[i] - self.file_change_intervals[i - 1]
                <= max_interval
            ]

            if filtered_intervals:
                avg_change_interval = sum(filtered_intervals) / len(filtered_intervals)
                changes_per_second = (
                    1 / avg_change_interval if avg_change_interval > 0 else 0
                )
            else:
                changes_per_second = 0

            total_processing_time = sum(self.file_processing_durations)
            processing_per_second = (
                len(self.file_processing_durations) / total_processing_time
                if total_processing_time > 0
                else 0
            )

            if changes_per_second > 0 and processing_per_second > 0:
                rate = changes_per_second / processing_per_second
                new_processing_interval = max(1, math.ceil(self.sparsity_factor * rate))

                current_time = time.time()
                if current_time - self.last_battery_check > self.battery_check_interval:
                    self.last_battery_check = current_time
                    is_on_battery.cache_clear()  # Clear the cache to get fresh battery status
                if is_on_battery():
                    new_processing_interval *= 2
                    self.logger.info(
                        "Running on battery, doubling the processing interval.",
                        extra={"log_type": "bg"}
                    )

                if new_processing_interval != self.processing_interval:
                    old_processing_interval = self.processing_interval
                    self.processing_interval = new_processing_interval
                    self.logger.info(
                        f"Processing interval: {old_processing_interval} -> {self.processing_interval}, "
                        f"Changes: {changes_per_second:.2f}it/s, "
                        f"Processing: {processing_per_second:.2f}it/s, "
                        f"Rate (changes/processing): {rate:.2f}",
                        extra={"log_type": "bg"}
                    )

    def is_valid_file(self, path):
        filename = os.path.basename(path)
        return (
            any(path.lower().endswith(ext) for ext in self.include_files)
            and not is_temp_file(filename)
            and not self.inode_pattern.match(filename)
        )

    def on_created(self, event):
        self.handle_event(event)

    def on_modified(self, event):
        self.handle_event(event)

    def on_moved(self, event):
        if self.handle_event(event):
            # For moved events, we need to update the key in pending_files
            with self.lock:
                self.pending_files[event.dest_path] = self.pending_files.pop(
                    event.src_path, {"timestamp": time.time(), "last_size": 0}
                )

    def on_deleted(self, event):
        if self.is_valid_file(event.src_path):
            self.logger.info(f"File deleted: {event.src_path}")
            # Remove from pending files if it was there
            with self.lock:
                self.pending_files.pop(event.src_path, None)
            # Add logic for handling deleted files if needed


@lib_app.command("watch")
def watch(
    library_id: int,
    folders: List[int] = typer.Option(
        None, "--folder", "-f", help="Specify folders to watch"
    ),
    sparsity_factor: float = typer.Option(
        3.0, "--sparsity-factor", "-sf", help="Sparsity factor for file processing"
    ),
    processing_interval: int = typer.Option(
        12,
        "--processing-interval",
        "-pi",
        help="Process one file with plugins for every N files (higher means less frequent processing)",
    ),
    rate_window_size: int = typer.Option(
        10,
        "--rate-window",
        "-rw",
        help="Number of recent events to consider when calculating processing rates",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
):
    """
    Watch for file changes in the library folders and sync automatically.
    """
    # Set the logging level based on the verbose flag
    log_level = "DEBUG" if verbose else "INFO"
    logger.setLevel(log_level)

    logger.info(f"Watching library {library_id} for changes...")

    # Get the library
    response = httpx.get(f"{BASE_URL}/api/libraries/{library_id}")
    if response.status_code != 200:
        print(f"Error: Library with id {library_id} not found.")
        raise typer.Exit(code=1)

    library = response.json()

    # Filter folders if the folders parameter is provided
    if folders:
        library_folders = [
            folder for folder in library["folders"] if folder["id"] in folders
        ]
    else:
        library_folders = library["folders"]

    if not library_folders:
        print("No folders to watch.")
        return

    # Create an observer and handler for each folder in the library
    observer = Observer()
    handlers = []
    for folder in library_folders:
        folder_path = Path(folder["path"])
        event_handler = LibraryFileHandler(
            library_id,
            include_files,
            sparsity_factor=sparsity_factor,
            processing_interval=processing_interval,
            rate_window_size=rate_window_size,
        )
        handlers.append(event_handler)
        observer.schedule(event_handler, str(folder_path), recursive=True)
        print(f"Watching folder: {folder_path}")

    observer.start()
    try:
        while True:
            time.sleep(5)
            app_name, _, _ = get_active_window_info()
            if is_app_blacklisted(app_name):
                # If app is blacklisted, clear all pending files from handlers
                for handler in handlers:
                    with handler.lock:
                        if handler.pending_files:
                            handler.logger.info(f"App '{app_name}' is blacklisted. Clearing {len(handler.pending_files)} pending files", 
                                                extra={"log_type": "bg"})
                            handler.pending_files.clear()
            else:
                for handler in handlers:
                    handler.process_pending_files()
    except KeyboardInterrupt:
        observer.stop()
        for handler in handlers:
            handler.executor.shutdown(wait=True)
    observer.join()


async def collect_candidate_files(folder_path: Path) -> List[str]:
    """
    Collect candidate files to be processed

    Args:
        folder_path: Folder path

    Returns:
        List[str]: List of candidate file paths
    """
    candidate_files = []
    for root, _, files in os.walk(folder_path):
        with tqdm(total=len(files), desc=f"Scanning {root}", leave=True) as pbar:
            for file in files:
                file_path = Path(root) / file
                absolute_file_path = file_path.resolve()

                # Check if the file extension is in the include_files list and is not a temporary file
                if file_path.suffix.lower() in include_files and not is_temp_file(file):
                    candidate_files.append(str(absolute_file_path))
                pbar.update(1)

    return candidate_files


async def prepare_entity(file_path: str, folder_id: int) -> Dict[str, Any]:
    """
    Prepare entity data

    Args:
        file_path: File path
        folder_id: Folder ID

    Returns:
        Dict[str, Any]: Entity data
    """
    file_path = Path(file_path)
    file_stat = file_path.stat()
    file_type, file_type_group = get_file_type(file_path)

    # 比较st_mtime和st_ctime，使用较早的时间作为file_created_at
    created_at_timestamp = file_stat.st_ctime
    if file_stat.st_mtime < file_stat.st_ctime:
        created_at_timestamp = file_stat.st_mtime

    new_entity = {
        "filename": file_path.name,
        "filepath": str(file_path),
        "size": file_stat.st_size,
        "file_created_at": format_timestamp(created_at_timestamp),
        "file_last_modified_at": format_timestamp(file_stat.st_mtime),
        "file_type": file_type,
        "file_type_group": file_type_group,
        "folder_id": folder_id,
    }

    # Handle image metadata
    is_thumbnail = False
    metadata_timestamp = None  # Default: no timestamp from metadata
    if file_type_group == "image":
        metadata = get_image_metadata(file_path)
        if metadata:
            # Use parse_timestamp_from_metadata to get the timestamp
            metadata_timestamp = parse_timestamp_from_metadata(metadata)
            if "active_window" in metadata and "active_app" not in metadata:
                metadata["active_app"] = metadata["active_window"].split(" - ")[0]
            new_entity["metadata_entries"] = [
                {
                    "key": key,
                    "value": str(value),
                    "source": MetadataSource.SYSTEM_GENERATED.value,
                    "data_type": (
                        "number" if isinstance(value, (int, float)) else "text"
                    ),
                }
                for key, value in metadata.items()
                if key != IS_THUMBNAIL
            ]
            if "active_app" in metadata:
                new_entity.setdefault("tags", []).append(metadata["active_app"])
            is_thumbnail = metadata.get(IS_THUMBNAIL, False)

            if is_thumbnail:
                typer.echo(f"Skipping thumbnail file: {file_path}")
                return

    # If metadata_timestamp is set, use it for file_created_at
    if metadata_timestamp is not None:
        new_entity["file_created_at"] = format_timestamp(metadata_timestamp)

    new_entity["is_thumbnail"] = is_thumbnail
    return new_entity


def format_error_message(
    file_status: FileStatus, response: Optional[httpx.Response]
) -> str:
    """
    Format error message

    Args:
        file_status: File status
        response: HTTP response

    Returns:
        str: Formatted error message
    """
    action = "add" if file_status == FileStatus.ADDED else "update"
    error_message = f"Failed to {action} file"

    if response:
        if hasattr(response, "status_code"):
            error_message += f": {response.status_code}"
        if hasattr(response, "text"):
            error_message += f" - {response.text}"
    else:
        error_message += " - Unknown error occurred"

    return error_message


async def process_file_batches(
    client: httpx.AsyncClient,
    library: dict,
    folder: dict,
    candidate_files: list,
    force: bool,
    plugins: list,
    semaphore: asyncio.Semaphore,
) -> Tuple[int, int]:
    """
    Process file batches

    Args:
        client: httpx async client
        library: Library object
        folder: Folder information
        candidate_files: List of candidate files
        force: Whether to force update
        plugins: List of plugins
        semaphore: Concurrency control semaphore

    Returns:
        Tuple[int, int]: (Number of files added, Number of files updated)
    """
    added_file_count = 0
    updated_file_count = 0
    batching = 50

    library_id = library.get("id")
    library_plugins = [plugin.get("id") for plugin in library.get("plugins", [])]
    target_plugins = (
        library_plugins
        if plugins is None
        else [plugin for plugin in library_plugins if plugin in plugins]
    )

    with tqdm(total=len(candidate_files), desc="Processing files", leave=True) as pbar:
        for i in range(0, len(candidate_files), batching):
            batch = candidate_files[i : i + batching]

            # Get existing entities in the batch
            get_response = await client.post(
                f"{BASE_URL}/api/libraries/{library_id}/entities/by-filepaths",
                json=batch,
            )

            if get_response.status_code != 200:
                print(
                    f"Failed to get entities: {get_response.status_code} - {get_response.text}"
                )
                pbar.update(len(batch))
                continue

            existing_entities = get_response.json()
            existing_entities_dict = {
                entity["filepath"]: entity for entity in existing_entities
            }

            # Process each file
            tasks = []
            for file_path in batch:
                new_entity = await prepare_entity(file_path, folder["id"])

                if new_entity.get("is_thumbnail", False):
                    typer.echo(f"Skipping thumbnail file: {file_path}")
                    continue

                existing_entity = existing_entities_dict.get(str(file_path))
                if existing_entity:
                    if force:
                        # Directly update without merging if force is true
                        tasks.append(
                            update_entity(
                                client, semaphore, plugins, new_entity, existing_entity, force
                            )
                        )
                    else:
                        # Merge existing metadata with new metadata
                        new_metadata_keys = {
                            entry["key"]
                            for entry in new_entity.get("metadata_entries", [])
                        }
                        for existing_entry in existing_entity.get(
                            "metadata_entries", []
                        ):
                            if existing_entry["key"] not in new_metadata_keys:
                                new_entity.setdefault("metadata_entries", []).append(
                                    existing_entry
                                )

                        # Merge existing tags with new tags
                        existing_tags = {
                            tag["name"] for tag in existing_entity.get("tags", [])
                        }
                        new_tags = set(new_entity.get("tags", []))
                        merged_tags = new_tags.union(existing_tags)
                        new_entity["tags"] = list(merged_tags)

                        # Check if the entity needs to be processed by any plugins
                        processed_plugins = {
                            plugin_status.get("plugin_id")
                            for plugin_status in existing_entity.get(
                                "plugin_status", []
                            )
                        }
                        has_unprocessed_plugins = any(
                            plugin_id not in processed_plugins
                            for plugin_id in target_plugins
                        )

                        # Only update if there are actual changes or the entity needs to be processed by any plugins
                        if has_unprocessed_plugins or has_entity_changes(
                            new_entity, existing_entity
                        ):
                            tasks.append(
                                update_entity(
                                    client,
                                    semaphore,
                                    plugins,
                                    new_entity,
                                    existing_entity,
                                    force
                                )
                            )
                        else:
                            pbar.write(
                                f"Skipping file: {file_path} #{existing_entity.get('id')}"
                            )
                            pbar.update(1)
                            continue
                else:
                    tasks.append(
                        add_entity(client, semaphore, library_id, plugins, new_entity)
                    )

            # Process task results
            if tasks:
                for future in asyncio.as_completed(tasks):
                    file_path, file_status, succeeded, response = await future
                    if succeeded:
                        if file_status == FileStatus.ADDED:
                            added_file_count += 1
                            tqdm.write(f"Added file to library: {file_path}")
                        else:
                            updated_file_count += 1
                            tqdm.write(f"Updated file in library: {file_path}")
                    else:
                        error_message = format_error_message(file_status, response)
                        tqdm.write(error_message)

                    # Update progress bar for each file processed
                    pbar.update(1)
                    pbar.set_postfix(
                        {"Added": added_file_count, "Updated": updated_file_count},
                        refresh=True,
                    )

    return added_file_count, updated_file_count


async def check_deleted_files(
    client: httpx.AsyncClient,
    library_id: int,
    folder: dict,
    folder_path: Path,
    scanned_files: Set[str],
) -> int:
    """
    Check and handle deleted files

    Args:
        client: httpx async client
        library_id: Library ID
        folder: Folder information
        folder_path: Folder path
        scanned_files: Set of scanned files

    Returns:
        int: Number of deleted files
    """
    deleted_count = 0
    limit = 100
    offset = 0
    total_entities = 0

    with tqdm(
        total=total_entities, desc="Checking for deleted files", leave=True
    ) as pbar:
        while True:
            # Add path_prefix parameter to only get entities under the folder_path
            existing_files_response = await client.get(
                f"{BASE_URL}/api/libraries/{library_id}/folders/{folder['id']}/entities",
                params={
                    "limit": limit,
                    "offset": offset,
                    "path_prefix": str(folder_path),
                },
                timeout=300,
            )

            if existing_files_response.status_code != 200:
                pbar.write(
                    f"Failed to retrieve existing files: {existing_files_response.status_code} - {existing_files_response.text}"
                )
                break

            existing_files = existing_files_response.json()
            if not existing_files:
                break

            # Update total count (if this is the first request)
            if offset == 0:
                total_entities = int(
                    existing_files_response.headers.get("X-Total-Count", total_entities)
                )
                pbar.total = total_entities
                pbar.refresh()

            for existing_file in existing_files:
                if (
                    # path_prefix may include files not in the folder_path,
                    # for example when folder_path is 20241101 but there is another folder 20241101-copy
                    # so check the existing_file is relative_to folder_path is required,
                    # do not remove this.
                    Path(existing_file["filepath"]).is_relative_to(folder_path)
                    and existing_file["filepath"] not in scanned_files
                ):
                    # File has been deleted
                    delete_response = await client.delete(
                        f"{BASE_URL}/api/libraries/{library_id}/entities/{existing_file['id']}"
                    )
                    if 200 <= delete_response.status_code < 300:
                        pbar.write(
                            f"Deleted file from library: {existing_file['filepath']}"
                        )
                        deleted_count += 1
                    else:
                        pbar.write(
                            f"Failed to delete file: {delete_response.status_code} - {delete_response.text}"
                        )
                pbar.update(1)

            offset += limit

    return deleted_count


def parse_timestamp_from_metadata(metadata: dict) -> float | str | None:
    """
    Parse the 'timestamp' field from metadata if present, in 'YYYYMMDD-HHMMSS' UTC format.
    Returns a float timestamp (seconds since epoch) if successful, otherwise the original value or None.
    """
    ts = metadata.get("timestamp")
    if not ts:
        return None
    try:
        dt = datetime.strptime(ts, "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return ts

