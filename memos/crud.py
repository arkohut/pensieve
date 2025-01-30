import logfire
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, text, BigInteger
from .schemas import (
    Library,
    NewLibraryParam,
    Folder,
    NewEntityParam,
    Entity,
    Plugin,
    NewPluginParam,
    UpdateEntityParam,
    NewFoldersParam,
    MetadataSource,
    EntityMetadataParam,
)
from .models import (
    LibraryModel,
    FolderModel,
    EntityModel,
    EntityModel,
    PluginModel,
    LibraryPluginModel,
    TagModel,
    EntityMetadataModel,
    EntityTagModel,
    EntityPluginStatusModel,
)
from collections import defaultdict
from .embedding import get_embeddings
import logging
from sqlite_vec import serialize_float32
import time
import json
from sqlalchemy.sql import text, bindparam
from datetime import datetime
from sqlalchemy.orm import joinedload, selectinload
from .search import create_search_provider

logger = logging.getLogger(__name__)


def get_library_by_id(library_id: int, db: Session) -> Library | None:
    return db.query(LibraryModel).filter(LibraryModel.id == library_id).first()


def create_library(library: NewLibraryParam, db: Session) -> Library:
    db_library = LibraryModel(name=library.name)
    db.add(db_library)
    db.commit()
    db.refresh(db_library)

    for folder in library.folders:
        db_folder = FolderModel(
            path=str(folder.path),
            library_id=db_library.id,
            last_modified_at=folder.last_modified_at,
            type=folder.type,
        )
        db.add(db_folder)

    db.commit()
    return Library(
        id=db_library.id,
        name=db_library.name,
        folders=[
            Folder(
                id=db_folder.id,
                path=db_folder.path,
                last_modified_at=db_folder.last_modified_at,
                type=db_folder.type,
            )
            for db_folder in db_library.folders
        ],
        plugins=[],
    )


def get_libraries(db: Session) -> List[Library]:
    return db.query(LibraryModel).order_by(LibraryModel.id.asc()).all()


def get_library_by_name(library_name: str, db: Session) -> Library | None:
    return (
        db.query(LibraryModel)
        .filter(func.lower(LibraryModel.name) == library_name.lower())
        .first()
    )


def add_folders(library_id: int, folders: NewFoldersParam, db: Session) -> Library:
    for folder in folders.folders:
        db_folder = FolderModel(
            path=str(folder.path),
            library_id=library_id,
            last_modified_at=folder.last_modified_at,
            type=folder.type,
        )
        db.add(db_folder)
        db.commit()
        db.refresh(db_folder)

    db_library = db.query(LibraryModel).filter(LibraryModel.id == library_id).first()
    return Library(**db_library.__dict__)


def create_entity(
    library_id: int,
    entity: NewEntityParam,
    db: Session,
) -> Entity:
    tags = entity.tags
    metadata_entries = entity.metadata_entries

    # Remove tags and metadata_entries from entity
    entity.tags = None
    entity.metadata_entries = None

    db_entity = EntityModel(
        **entity.model_dump(exclude_none=True), library_id=library_id
    )
    db.add(db_entity)
    db.commit()
    db.refresh(db_entity)

    # Handle tags separately
    if tags:
        for tag_name in tags:
            tag = db.query(TagModel).filter(TagModel.name == tag_name).first()
            if not tag:
                tag = TagModel(name=tag_name)
                db.add(tag)
                db.commit()
                db.refresh(tag)
            entity_tag = EntityTagModel(
                entity_id=db_entity.id,
                tag_id=tag.id,
                source=MetadataSource.PLUGIN_GENERATED,
            )
            db.add(entity_tag)
        db.commit()

    # Handle attrs separately
    if metadata_entries:
        for attr in metadata_entries:
            entity_metadata = EntityMetadataModel(
                entity_id=db_entity.id,
                key=attr.key,
                value=attr.value,
                source=attr.source,
                source_type=MetadataSource.PLUGIN_GENERATED if attr.source else None,
                data_type=attr.data_type,
            )
            db.add(entity_metadata)
    db.commit()
    db.refresh(db_entity)

    return Entity(**db_entity.__dict__)


def get_entity_by_id(entity_id: int, db: Session) -> Entity | None:
    return db.query(EntityModel).filter(EntityModel.id == entity_id).first()


def get_entities_of_folder(
    library_id: int,
    folder_id: int,
    db: Session,
    limit: int = 10,
    offset: int = 0,
    path_prefix: str | None = None,
) -> Tuple[List[Entity], int]:
    # First get the entity IDs with limit and offset
    id_query = (
        db.query(EntityModel.id)
        .filter(
            EntityModel.folder_id == folder_id,
            EntityModel.library_id == library_id,
        )
        .order_by(EntityModel.file_last_modified_at.asc())
    )

    # Add path_prefix filter if provided
    if path_prefix:
        id_query = id_query.filter(EntityModel.filepath.like(f"{path_prefix}%"))

    total_count = id_query.count()
    entity_ids = id_query.limit(limit).offset(offset).all()
    entity_ids = [id[0] for id in entity_ids]

    # Then get the full entities with relationships for those IDs
    entities = (
        db.query(EntityModel)
        .options(
            joinedload(EntityModel.metadata_entries),
            joinedload(EntityModel.tags),
            joinedload(EntityModel.plugin_status)
        )
        .filter(EntityModel.id.in_(entity_ids))
        .order_by(EntityModel.file_last_modified_at.asc())
        .all()
    )

    return entities, total_count


def get_entity_by_filepath(filepath: str, db: Session) -> Entity | None:
    return db.query(EntityModel).filter(EntityModel.filepath == filepath).first()


def get_entities_by_filepaths(filepaths: List[str], db: Session) -> List[Entity]:
    return (
        db.query(EntityModel)
        .options(
            joinedload(EntityModel.metadata_entries),
            joinedload(EntityModel.tags),
            joinedload(EntityModel.plugin_status),
        )
        .filter(EntityModel.filepath.in_(filepaths))
        .all()
    )


def remove_entity(entity_id: int, db: Session):
    entity = db.query(EntityModel).filter(EntityModel.id == entity_id).first()
    if entity:
        # Delete the entity from FTS and vec tables first
        db.execute(text("DELETE FROM entities_fts WHERE id = :id"), {"id": entity_id})
        db.execute(
            text("DELETE FROM entities_vec_v2 WHERE rowid = :id"), {"id": entity_id}
        )

        # Then delete the entity itself
        db.delete(entity)
        db.commit()
    else:
        raise ValueError(f"Entity with id {entity_id} not found")


def create_plugin(newPlugin: NewPluginParam, db: Session) -> Plugin:
    db_plugin = PluginModel(**newPlugin.model_dump(mode="json"))
    db.add(db_plugin)
    db.commit()
    db.refresh(db_plugin)
    return db_plugin


def get_plugins(db: Session) -> List[Plugin]:
    return db.query(PluginModel).order_by(PluginModel.id.asc()).all()


def get_plugin_by_name(plugin_name: str, db: Session) -> Plugin | None:
    return (
        db.query(PluginModel)
        .filter(func.lower(PluginModel.name) == plugin_name.lower())
        .first()
    )


def add_plugin_to_library(library_id: int, plugin_id: int, db: Session):
    library_plugin = LibraryPluginModel(library_id=library_id, plugin_id=plugin_id)
    db.add(library_plugin)
    db.commit()
    db.refresh(library_plugin)


def find_entities_by_ids(entity_ids: List[int], db: Session) -> List[Entity]:
    db_entities = (
        db.query(EntityModel)
        .options(joinedload(EntityModel.metadata_entries), joinedload(EntityModel.tags))
        .filter(EntityModel.id.in_(entity_ids))
        .all()
    )
    return [Entity(**entity.__dict__) for entity in db_entities]


def update_entity(
    entity_id: int,
    updated_entity: UpdateEntityParam,
    db: Session,
) -> Entity:
    db_entity = db.query(EntityModel).filter(EntityModel.id == entity_id).first()

    if db_entity is None:
        raise ValueError(f"Entity with id {entity_id} not found")

    # Update the main fields of the entity
    for key, value in updated_entity.model_dump().items():
        if key not in ["tags", "metadata_entries"] and value is not None:
            setattr(db_entity, key, value)

    # Handle tags separately
    if updated_entity.tags is not None:
        # Clear existing tags
        db.query(EntityTagModel).filter(EntityTagModel.entity_id == entity_id).delete()
        db.commit()

        for tag_name in updated_entity.tags:
            tag = db.query(TagModel).filter(TagModel.name == tag_name).first()
            if not tag:
                tag = TagModel(name=tag_name)
                db.add(tag)
                db.commit()
                db.refresh(tag)
            entity_tag = EntityTagModel(
                entity_id=db_entity.id,
                tag_id=tag.id,
                source=MetadataSource.PLUGIN_GENERATED,
            )
            db.add(entity_tag)
        db.commit()

    # Handle attrs separately
    if updated_entity.metadata_entries is not None:
        # Clear existing attrs
        db.query(EntityMetadataModel).filter(
            EntityMetadataModel.entity_id == entity_id
        ).delete()
        db.commit()

        for attr in updated_entity.metadata_entries:
            entity_metadata = EntityMetadataModel(
                entity_id=db_entity.id,
                key=attr.key,
                value=attr.value,
                source=attr.source if attr.source is not None else None,
                source_type=(
                    MetadataSource.PLUGIN_GENERATED if attr.source is not None else None
                ),
                data_type=attr.data_type,
            )
            db.add(entity_metadata)
            db_entity.metadata_entries.append(entity_metadata)

    db.commit()
    db.refresh(db_entity)

    return Entity(**db_entity.__dict__)


def touch_entity(entity_id: int, db: Session) -> bool:
    db_entity = db.query(EntityModel).filter(EntityModel.id == entity_id).first()
    if db_entity:
        db_entity.last_scan_at = func.now()
        db.commit()
        db.refresh(db_entity)
        return True
    else:
        return False


def update_entity_tags(
    entity_id: int,
    tags: List[str],
    db: Session,
) -> Entity:
    db_entity = get_entity_by_id(entity_id, db)
    if not db_entity:
        raise ValueError(f"Entity with id {entity_id} not found")

    # Clear existing tags
    db.query(EntityTagModel).filter(EntityTagModel.entity_id == entity_id).delete()

    for tag_name in tags:
        tag = db.query(TagModel).filter(TagModel.name == tag_name).first()
        if not tag:
            tag = TagModel(name=tag_name)
            db.add(tag)
            db.commit()
            db.refresh(tag)
        entity_tag = EntityTagModel(
            entity_id=db_entity.id,
            tag_id=tag.id,
            source=MetadataSource.PLUGIN_GENERATED,
        )
        db.add(entity_tag)

    # Update last_scan_at in the same transaction
    db_entity.last_scan_at = func.now()

    db.commit()
    db.refresh(db_entity)

    return Entity(**db_entity.__dict__)


def add_new_tags(entity_id: int, tags: List[str], db: Session) -> Entity:
    db_entity = get_entity_by_id(entity_id, db)
    if not db_entity:
        raise ValueError(f"Entity with id {entity_id} not found")

    existing_tags = set(tag.name for tag in db_entity.tags)
    new_tags = set(tags) - existing_tags

    for tag_name in new_tags:
        tag = db.query(TagModel).filter(TagModel.name == tag_name).first()
        if not tag:
            tag = TagModel(name=tag_name)
            db.add(tag)
            db.commit()
            db.refresh(tag)
        entity_tag = EntityTagModel(
            entity_id=db_entity.id,
            tag_id=tag.id,
            source=MetadataSource.PLUGIN_GENERATED,
        )
        db.add(entity_tag)

    # Update last_scan_at in the same transaction
    db_entity.last_scan_at = func.now()

    db.commit()
    db.refresh(db_entity)

    return Entity(**db_entity.__dict__)


def update_entity_metadata_entries(
    entity_id: int,
    updated_metadata: List[EntityMetadataParam],
    db: Session,
) -> Entity:
    db_entity = get_entity_by_id(entity_id, db)

    existing_metadata_entries = (
        db.query(EntityMetadataModel)
        .filter(EntityMetadataModel.entity_id == db_entity.id)
        .all()
    )

    existing_metadata_dict = {entry.key: entry for entry in existing_metadata_entries}

    for metadata in updated_metadata:
        if metadata.key in existing_metadata_dict:
            existing_metadata = existing_metadata_dict[metadata.key]
            existing_metadata.value = metadata.value
            existing_metadata.source = (
                metadata.source
                if metadata.source is not None
                else existing_metadata.source
            )
            existing_metadata.source_type = (
                MetadataSource.PLUGIN_GENERATED
                if metadata.source is not None
                else existing_metadata.source_type
            )
            existing_metadata.data_type = metadata.data_type
        else:
            entity_metadata = EntityMetadataModel(
                entity_id=db_entity.id,
                key=metadata.key,
                value=metadata.value,
                source=metadata.source if metadata.source is not None else None,
                source_type=(
                    MetadataSource.PLUGIN_GENERATED
                    if metadata.source is not None
                    else None
                ),
                data_type=metadata.data_type,
            )
            db.add(entity_metadata)
            db_entity.metadata_entries.append(entity_metadata)

    # Update last_scan_at in the same transaction
    db_entity.last_scan_at = func.now()

    db.commit()
    db.refresh(db_entity)

    return Entity(**db_entity.__dict__)


def get_plugin_by_id(plugin_id: int, db: Session) -> Plugin | None:
    return db.query(PluginModel).filter(PluginModel.id == plugin_id).first()


def remove_plugin_from_library(library_id: int, plugin_id: int, db: Session):
    library_plugin = (
        db.query(LibraryPluginModel)
        .filter(
            LibraryPluginModel.library_id == library_id,
            LibraryPluginModel.plugin_id == plugin_id,
        )
        .first()
    )

    if library_plugin:
        db.delete(library_plugin)
        db.commit()
    else:
        raise ValueError(f"Plugin {plugin_id} not found in library {library_id}")


def list_entities(
    db: Session,
    limit: int = 200,
    library_ids: Optional[List[int]] = None,
    start: Optional[int] = None,
    end: Optional[int] = None,
) -> List[Entity]:
    query = (
        db.query(EntityModel)
        .options(joinedload(EntityModel.metadata_entries), joinedload(EntityModel.tags))
        .filter(EntityModel.file_type_group == "image")
    )

    if library_ids:
        query = query.filter(EntityModel.library_id.in_(library_ids))

    if start is not None and end is not None:
        # Convert timestamp to Unix timestamp using EXTRACT(EPOCH FROM timestamp)
        # This works in both PostgreSQL and SQLite (SQLite will use its own implementation)
        query = query.filter(
            func.extract('epoch', EntityModel.file_created_at).cast(BigInteger).between(start, end)
        )

    entities = query.order_by(EntityModel.file_created_at.desc()).limit(limit).all()

    return [Entity(**entity.__dict__) for entity in entities]


def get_entity_context(
    db: Session, library_id: int, entity_id: int, prev: int = 0, next: int = 0
) -> Tuple[List[Entity], List[Entity]]:
    """
    Get the context (previous and next entities) for a given entity.
    Returns a tuple of (previous_entities, next_entities).
    """
    # First get the target entity to get its timestamp
    target_entity = (
        db.query(EntityModel)
        .filter(
            EntityModel.id == entity_id,
            EntityModel.library_id == library_id,
        )
        .first()
    )

    if not target_entity:
        return [], []

    # Get previous entities
    prev_entities = []
    if prev > 0:
        prev_entities = (
            db.query(EntityModel)
            .filter(
                EntityModel.library_id == library_id,
                EntityModel.file_created_at < target_entity.file_created_at,
            )
            .order_by(EntityModel.file_created_at.desc())
            .limit(prev)
            .all()
        )
        # Reverse the list to get chronological order and convert to Entity models
        prev_entities = [Entity(**entity.__dict__) for entity in prev_entities][::-1]

    # Get next entities
    next_entities = []
    if next > 0:
        next_entities = (
            db.query(EntityModel)
            .filter(
                EntityModel.library_id == library_id,
                EntityModel.file_created_at > target_entity.file_created_at,
            )
            .order_by(EntityModel.file_created_at.asc())
            .limit(next)
            .all()
        )
        # Convert to Entity models
        next_entities = [Entity(**entity.__dict__) for entity in next_entities]

    return prev_entities, next_entities


def record_plugin_processed(entity_id: int, plugin_id: int, db: Session):
    """Record that an entity has been processed by a plugin"""
    status = EntityPluginStatusModel(entity_id=entity_id, plugin_id=plugin_id)
    db.merge(status)  # merge will insert or update
    db.commit()


def get_pending_plugins(entity_id: int, library_id: int, db: Session) -> List[int]:
    """Get list of plugin IDs that haven't processed this entity yet"""
    # Get all plugins associated with the library
    library_plugins = (
        db.query(PluginModel.id)
        .join(LibraryPluginModel)
        .filter(LibraryPluginModel.library_id == library_id)
        .all()
    )
    library_plugin_ids = [p.id for p in library_plugins]

    # Get plugins that have already processed this entity
    processed_plugins = (
        db.query(EntityPluginStatusModel.plugin_id)
        .filter(EntityPluginStatusModel.entity_id == entity_id)
        .all()
    )
    processed_plugin_ids = [p.plugin_id for p in processed_plugins]

    # Return plugins that need to process this entity
    return list(set(library_plugin_ids) - set(processed_plugin_ids))
