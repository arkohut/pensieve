import logfire
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, text
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
    return db.query(LibraryModel).all()


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
    query = (
        db.query(EntityModel)
        .options(joinedload(EntityModel.metadata_entries), joinedload(EntityModel.tags))
        .filter(
            EntityModel.folder_id == folder_id,
            EntityModel.library_id == library_id,
        )
    )

    # Add path_prefix filter if provided
    if path_prefix:
        query = query.filter(EntityModel.filepath.like(f"{path_prefix}%"))

    total_count = query.count()
    entities = query.limit(limit).offset(offset).all()

    return entities, total_count


def get_entity_by_filepath(filepath: str, db: Session) -> Entity | None:
    return db.query(EntityModel).filter(EntityModel.filepath == filepath).first()


def get_entities_by_filepaths(filepaths: List[str], db: Session) -> List[Entity]:
    return db.query(EntityModel).filter(EntityModel.filepath.in_(filepaths)).all()


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
    return db.query(PluginModel).all()


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


def and_words(input_string):
    words = input_string.split()
    result = " AND ".join(words)
    return result


def full_text_search(
    query: str,
    db: Session,
    limit: int = 200,
    library_ids: Optional[List[int]] = None,
    start: Optional[int] = None,
    end: Optional[int] = None,
    app_names: Optional[List[str]] = None,
) -> List[int]:
    start_time = time.time()

    and_query = and_words(query)

    sql_query = """
    WITH fts_matches AS (
        SELECT id, rank
        FROM entities_fts
        WHERE entities_fts MATCH jieba_query(:query)
    )
    SELECT e.id 
    FROM fts_matches f
    JOIN entities e ON e.id = f.id
    WHERE e.file_type_group = 'image'
    """

    params = {"query": and_query, "limit": limit}

    # Only add bindparams if the parameters are provided
    bindparams = []

    if library_ids:
        sql_query += " AND e.library_id IN :library_ids"
        params["library_ids"] = tuple(library_ids)
        bindparams.append(bindparam("library_ids", expanding=True))

    if start is not None and end is not None:
        sql_query += " AND strftime('%s', e.file_created_at, 'utc') BETWEEN :start AND :end"
        params["start"] = start
        params["end"] = end

    if app_names:
        sql_query += """
        AND EXISTS (
            SELECT 1 FROM metadata_entries me 
            WHERE me.entity_id = e.id 
            AND me.key = 'active_app' 
            AND me.value IN :app_names
        )
        """
        params["app_names"] = tuple(app_names)
        bindparams.append(bindparam("app_names", expanding=True))

    sql_query += " ORDER BY f.rank LIMIT :limit"

    # Only add bindparams if we have any
    sql = text(sql_query)
    if bindparams:
        sql = sql.bindparams(*bindparams)

    result = db.execute(sql, params).fetchall()

    execution_time = time.time() - start_time
    logger.info(f"Full-text search execution time: {execution_time:.4f} seconds")

    ids = [row[0] for row in result]
    return ids


def vec_search(
    query: str,
    db: Session,
    limit: int = 200,
    library_ids: Optional[List[int]] = None,
    start: Optional[int] = None,
    end: Optional[int] = None,
    app_names: Optional[List[str]] = None,
) -> List[int]:
    with logfire.span("get_embeddings for {query=}", query=query):
        query_embedding = get_embeddings([f"{query}"])

    if not query_embedding:
        return []

    query_embedding = query_embedding[0]

    start_date = None
    end_date = None
    if start is not None and end is not None:
        start_date = datetime.fromtimestamp(start).strftime("%Y-%m-%d")
        end_date = datetime.fromtimestamp(end).strftime("%Y-%m-%d")

    sql_query = f"""
    SELECT rowid
    FROM entities_vec_v2
    WHERE embedding MATCH :embedding
      AND file_type_group = 'image'
      AND K = :limit
      {"AND file_created_at_date BETWEEN :start_date AND :end_date" if start_date is not None and end_date is not None else ""}
      {"AND file_created_at_timestamp BETWEEN :start AND :end" if start is not None and end is not None else ""}
      {"AND library_id IN :library_ids" if library_ids else ""}
      {"AND app_name IN :app_names" if app_names else ""}
    ORDER BY distance ASC
    """

    params = {
        "embedding": serialize_float32(query_embedding),
        "limit": limit,
    }

    if start is not None and end is not None:
        params["start"] = int(start)
        params["end"] = int(end)
        params["start_date"] = start_date
        params["end_date"] = end_date
    if library_ids:
        params["library_ids"] = tuple(library_ids)
    if app_names:
        params["app_names"] = tuple(app_names)

    # Bind parameters with expanding=True for app_names and library_ids
    sql = text(sql_query)
    if app_names:
        sql = sql.bindparams(bindparam("app_names", expanding=True))
    if library_ids:
        sql = sql.bindparams(bindparam("library_ids", expanding=True))

    with logfire.span("vec_search inside {query=}", query=query):
        result = db.execute(sql, params).fetchall()

    ids = [row[0] for row in result]
    # logger.info(f"SQL: {sql_query}")
    # logger.info(f"Params: {params}")
    # logger.info(f"Vector search results: {ids}")

    return ids


def reciprocal_rank_fusion(
    fts_results: List[int], vec_results: List[int], k: int = 60
) -> List[Tuple[int, float]]:
    rank_dict = defaultdict(float)

    # Weight for full-text search results: 0.7
    for rank, result_id in enumerate(fts_results):
        rank_dict[result_id] += 0.7 * (1 / (k + rank + 1))

    # Weight for vector search results: 0.3  
    for rank, result_id in enumerate(vec_results):
        rank_dict[result_id] += 0.3 * (1 / (k + rank + 1))

    sorted_results = sorted(rank_dict.items(), key=lambda x: x[1], reverse=True)
    return sorted_results


def hybrid_search(
    query: str,
    db: Session,
    limit: int = 200,
    library_ids: Optional[List[int]] = None,
    start: Optional[int] = None,
    end: Optional[int] = None,
    app_names: Optional[List[str]] = None,
    use_facet: bool = False,
) -> Tuple[List[Entity], dict]:

    with logfire.span("full_text_search"):
        fts_results = full_text_search(
            query, db, limit, library_ids, start, end, app_names
        )
    logger.info(f"Full-text search obtained {len(fts_results)} results")

    with logfire.span("vector_search"):
        vec_results = vec_search(
            query, db, limit * 2, library_ids, start, end, app_names
        )
    logger.info(f"Vector search obtained {len(vec_results)} results")

    with logfire.span("reciprocal_rank_fusion"):
        combined_results = reciprocal_rank_fusion(fts_results, vec_results)

    sorted_ids = [id for id, _ in combined_results][:limit]
    logger.info(f"Hybrid search results (sorted IDs): {sorted_ids}")

    with logfire.span("find_entities_by_ids"):
        entities = find_entities_by_ids(sorted_ids, db)

    entity_dict = {entity.id: entity for entity in entities}
    result = [entity_dict[id] for id in sorted_ids]

    if use_facet:
        with logfire.span("get_search_stats"):
            stats = get_search_stats(query, db, library_ids, start, end, app_names)
    else:
        stats = {}

    return result, stats


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
        query = query.filter(
            func.strftime("%s", EntityModel.file_created_at, "utc").between(
                str(start), str(end)
            )
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


def process_ocr_result(value, max_length=4096):
    try:
        ocr_data = json.loads(value)
        if isinstance(ocr_data, list) and all(
            isinstance(item, dict)
            and "dt_boxes" in item
            and "rec_txt" in item
            and "score" in item
            for item in ocr_data
        ):
            return " ".join(item["rec_txt"] for item in ocr_data[:max_length])
        else:
            return json.dumps(ocr_data, indent=2)
    except json.JSONDecodeError:
        return value


def prepare_fts_data(entity: EntityModel) -> tuple[str, str]:
    tags = ", ".join(entity.tag_names)
    fts_metadata = "\n".join(
        [
            f"{entry.key}: {process_ocr_result(entry.value) if entry.key == 'ocr_result' else entry.value}"
            for entry in entity.metadata_entries
        ]
    )
    return tags, fts_metadata


def prepare_vec_data(entity: EntityModel) -> str:
    vec_metadata = "\n".join(
        [
            f"{entry.key}: {entry.value}"
            for entry in entity.metadata_entries
            if entry.key not in ["ocr_result", "sequence"]
        ]
    )
    ocr_result = next(
        (entry.value for entry in entity.metadata_entries if entry.key == "ocr_result"),
        "",
    )
    vec_metadata += f"\nocr_result: {process_ocr_result(ocr_result, max_length=128)}"
    return vec_metadata


def update_entity_index(entity_id: int, db: Session):
    """Update both FTS and vector indexes for an entity"""
    try:
        entity = get_entity_by_id(entity_id, db)
        if not entity:
            raise ValueError(f"Entity with id {entity_id} not found")

        # Update FTS index
        tags, fts_metadata = prepare_fts_data(entity)
        db.execute(
            text(
                """
                INSERT OR REPLACE INTO entities_fts(id, filepath, tags, metadata)
                VALUES(:id, :filepath, :tags, :metadata)
                """
            ),
            {
                "id": entity.id,
                "filepath": entity.filepath,
                "tags": tags,
                "metadata": fts_metadata,
            },
        )

        # Update vector index
        vec_metadata = prepare_vec_data(entity)
        with logfire.span("get embedding for entity metadata"):
            embeddings = get_embeddings([vec_metadata])
            logfire.info(f"vec_metadata: {vec_metadata}")

        if embeddings and embeddings[0]:
            db.execute(
                text("DELETE FROM entities_vec_v2 WHERE rowid = :id"), {"id": entity.id}
            )

            # Extract app_name from metadata_entries
            app_name = next(
                (
                    entry.value
                    for entry in entity.metadata_entries
                    if entry.key == "active_app"
                ),
                "unknown",  # Default to 'unknown' if not found
            )
            # Get file_type_group from entity
            file_type_group = entity.file_type_group or "unknown"

            # Convert file_created_at to integer timestamp
            created_at_timestamp = int(entity.file_created_at.timestamp())

            db.execute(
                text(
                    """
                    INSERT INTO entities_vec_v2 (
                        rowid, embedding, app_name, file_type_group, created_at_timestamp, file_created_at_timestamp,
                        file_created_at_date, library_id
                    )
                    VALUES (:id, :embedding, :app_name, :file_type_group, :created_at_timestamp, :file_created_at_timestamp, :file_created_at_date, :library_id)
                    """
                ),
                {
                    "id": entity.id,
                    "embedding": serialize_float32(embeddings[0]),
                    "app_name": app_name,
                    "file_type_group": file_type_group,
                    "created_at_timestamp": created_at_timestamp,
                    "file_created_at_timestamp": int(
                        entity.file_created_at.timestamp()
                    ),
                    "file_created_at_date": entity.file_created_at.strftime("%Y-%m-%d"),
                    "library_id": entity.library_id,
                },
            )

        db.commit()
    except Exception as e:
        logger.error(f"Error updating indexes for entity {entity.id}: {e}")
        db.rollback()
        raise


def batch_update_entity_indices(entity_ids: List[int], db: Session):
    """Batch update both FTS and vector indexes for multiple entities"""
    try:
        entities = (
            db.query(EntityModel)
            .filter(EntityModel.id.in_(entity_ids))
            .options(
                selectinload(EntityModel.metadata_entries), selectinload(EntityModel.tags)
            )
            .all()
        )
        found_ids = {entity.id for entity in entities}

        missing_ids = set(entity_ids) - found_ids
        if missing_ids:
            raise ValueError(f"Entities not found: {missing_ids}")

        # Check existing vector indices and their timestamps
        existing_vec_indices = db.execute(
            text(
                """
                SELECT rowid, created_at_timestamp
                FROM entities_vec_v2
                WHERE rowid IN :entity_ids
            """
            ).bindparams(bindparam("entity_ids", expanding=True)),
            {"entity_ids": tuple(entity_ids)},
        ).fetchall()

        # Create lookup of vector index timestamps
        vec_timestamps = {row[0]: row[1] for row in existing_vec_indices}

        # Separate entities that need indexing
        needs_index = []

        for entity in entities:
            entity_last_scan = int(entity.last_scan_at.timestamp())
            vec_timestamp = vec_timestamps.get(entity.id, 0)

            # Entity needs full indexing if last_scan_at is
            # more recent than the vector index timestamp
            if entity_last_scan > vec_timestamp:
                needs_index.append(entity)

        logger.info(
            f"Entities needing full indexing: {len(needs_index)}/{len(entity_ids)}"
        )

        # Handle entities needing full indexing
        if needs_index:
            vec_metadata_list = [prepare_vec_data(entity) for entity in needs_index]
            with logfire.span("get embedding in batch indexing"):
                embeddings = get_embeddings(vec_metadata_list)
                logfire.info(f"vec_metadata_list: {vec_metadata_list}")

            # Delete all existing vector indices in one query
            if needs_index:
                db.execute(
                    text("DELETE FROM entities_vec_v2 WHERE rowid IN :ids").bindparams(
                        bindparam("ids", expanding=True)
                    ),
                    {"ids": tuple(entity.id for entity in needs_index)},
                )

                # Prepare batch insert data
                created_at_timestamp = int(datetime.now().timestamp())
                insert_values = []
                for entity, embedding in zip(needs_index, embeddings):
                    app_name = next(
                        (
                            entry.value
                            for entry in entity.metadata_entries
                            if entry.key == "active_app"
                        ),
                        "unknown",
                    )
                    file_type_group = entity.file_type_group or "unknown"

                    insert_values.append(
                        {
                            "id": entity.id,
                            "embedding": serialize_float32(embedding),
                            "app_name": app_name,
                            "file_type_group": file_type_group,
                            "created_at_timestamp": created_at_timestamp,
                            "file_created_at_timestamp": int(
                                entity.file_created_at.timestamp()
                            ),
                            "file_created_at_date": entity.file_created_at.strftime(
                                "%Y-%m-%d"
                            ),
                            "library_id": entity.library_id,
                        }
                    )

                # Execute batch insert
                db.execute(
                    text(
                        """
                        INSERT INTO entities_vec_v2 (
                            rowid, embedding, app_name, file_type_group,
                            created_at_timestamp, file_created_at_timestamp,
                            file_created_at_date, library_id
                        )
                        VALUES (
                            :id, :embedding, :app_name, :file_type_group,
                            :created_at_timestamp, :file_created_at_timestamp,
                            :file_created_at_date, :library_id
                        )
                    """
                    ),
                    insert_values,
                )

        # Update FTS index for all entities
        for entity in entities:
            tags, fts_metadata = prepare_fts_data(entity)
            db.execute(
                text(
                    """
                    INSERT OR REPLACE INTO entities_fts(id, filepath, tags, metadata)
                    VALUES(:id, :filepath, :tags, :metadata)
                """
                ),
                {
                    "id": entity.id,
                    "filepath": entity.filepath,
                    "tags": tags,
                    "metadata": fts_metadata,
                },
            )

        db.commit()

    except Exception as e:
        logger.error(f"Error batch updating indexes: {e}")
        db.rollback()
        raise


def get_search_stats(
    query: str,
    db: Session,
    library_ids: Optional[List[int]] = None,
    start: Optional[int] = None,
    end: Optional[int] = None,
    app_names: Optional[List[str]] = None,
) -> dict:
    """Get statistics for search results including date range and tag counts."""

    MIN_SAMPLE_SIZE = 2048
    MAX_SAMPLE_SIZE = 4096

    with logfire.span(
        "full_text_search in stats {query=} {limit=}",
        query=query,
        limit=MAX_SAMPLE_SIZE,
    ):
        fts_results = full_text_search(
            query,
            db,
            limit=MAX_SAMPLE_SIZE,
            library_ids=library_ids,
            start=start,
            end=end,
            app_names=app_names,
        )

    vec_limit = max(min(len(fts_results) * 2, MAX_SAMPLE_SIZE), MIN_SAMPLE_SIZE)

    with logfire.span(
        "vec_search in stats {query=} {limit=}", query=query, limit=vec_limit
    ):
        vec_results = vec_search(
            query,
            db,
            limit=vec_limit,
            library_ids=library_ids,
            start=start,
            end=end,
            app_names=app_names,
        )

    logfire.info(f"fts_results: {len(fts_results)} vec_results: {len(vec_results)}")

    entity_ids = set(fts_results + vec_results)

    if not entity_ids:
        return {"date_range": {"earliest": None, "latest": None}, "app_name_counts": {}}

    entity_ids_str = ",".join(str(id) for id in entity_ids)
    date_range = db.execute(
        text(
            f"""
            SELECT 
                MIN(file_created_at) as earliest,
                MAX(file_created_at) as latest
            FROM entities
            WHERE id IN ({entity_ids_str})
        """
        )
    ).first()

    app_name_counts = db.execute(
        text(
            f"""
            SELECT me.value, COUNT(*) as count
            FROM metadata_entries me
            WHERE me.entity_id IN ({entity_ids_str}) and me.key = 'active_app'
            GROUP BY me.value
            ORDER BY count DESC
        """
        )
    ).all()

    return {
        "date_range": {"earliest": date_range.earliest, "latest": date_range.latest},
        "app_name_counts": {app_name: count for app_name, count in app_name_counts},
    }


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
