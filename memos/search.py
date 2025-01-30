from abc import ABC, abstractmethod
from sqlalchemy import text, bindparam
from sqlalchemy.orm import Session
from typing import List, Optional, Tuple
import time
import logging
import logfire
from sqlite_vec import serialize_float32
from collections import defaultdict
from datetime import datetime
from .embedding import get_embeddings
import json
import jieba
import os

logger = logging.getLogger(__name__)


class SearchProvider(ABC):
    @abstractmethod
    def full_text_search(
        self,
        query: str,
        db: Session,
        limit: int,
        library_ids: Optional[List[int]] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        app_names: Optional[List[str]] = None,
    ) -> List[int]:
        pass

    @abstractmethod
    def vector_search(
        self,
        embeddings: List[float],
        db: Session,
        limit: int,
        library_ids: Optional[List[int]] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        app_names: Optional[List[str]] = None,
    ) -> List[int]:
        pass

    @abstractmethod
    def update_entity_index(self, entity_id: int, db: Session):
        """Update both FTS and vector indexes for an entity"""
        pass

    @abstractmethod
    def batch_update_entity_indices(self, entity_ids: List[int], db: Session):
        """Batch update both FTS and vector indexes for multiple entities"""
        pass

    @abstractmethod
    def get_search_stats(
        self,
        query: str,
        db: Session,
        library_ids: Optional[List[int]] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        app_names: Optional[List[str]] = None,
    ) -> dict:
        """Get statistics for search results including date range and app name counts."""
        pass

    def prepare_vec_data(self, entity) -> str:
        """Prepare metadata for vector embedding.

        Args:
            entity: The entity object containing metadata entries

        Returns:
            str: Processed metadata string for vector embedding
        """
        vec_metadata = "\n".join(
            [
                f"{entry.key}: {entry.value}"
                for entry in entity.metadata_entries
                if entry.key not in ["ocr_result", "sequence"]
            ]
        )
        ocr_result = next(
            (
                entry.value
                for entry in entity.metadata_entries
                if entry.key == "ocr_result"
            ),
            "",
        )
        vec_metadata += (
            f"\nocr_result: {self.process_ocr_result(ocr_result, max_length=128)}"
        )
        return vec_metadata

    def process_ocr_result(self, value, max_length=4096):
        """Process OCR result data.

        Args:
            value: OCR result data as string
            max_length: Maximum number of items to process

        Returns:
            str: Processed OCR result
        """
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


class PostgreSQLSearchProvider(SearchProvider):
    """
    PostgreSQL implementation of SearchProvider.
    """

    def tokenize_text(self, text: str) -> str:
        """Tokenize text using jieba for both Chinese and English text."""
        if not text:
            return ""
        # Tokenize the text using jieba
        words = jieba.cut(text)
        # Join with spaces for PostgreSQL full-text search
        return " ".join(words)

    def prepare_fts_data(self, entity) -> tuple[str, str, str]:
        """Prepare data for full-text search with jieba tokenization."""
        # Process filepath: keep directory structure but normalize separators
        # Also extract the filename without extension for better searchability
        filepath = entity.filepath.replace("\\", "/")  # normalize separators
        filename = os.path.basename(filepath)
        filename_without_ext = os.path.splitext(filename)[0]
        # Split filename by common separators (-, _, etc) to make parts searchable
        filename_parts = filename_without_ext.replace("-", " ").replace("_", " ")
        processed_filepath = f"{filepath} {filename_parts}"

        # Tokenize tags
        tags = " ".join(entity.tag_names)
        tokenized_tags = self.tokenize_text(tags)

        # Tokenize metadata
        metadata_entries = [
            f"{entry.key}: {self.process_ocr_result(entry.value) if entry.key == 'ocr_result' else entry.value}"
            for entry in entity.metadata_entries
        ]
        metadata = "\n".join(metadata_entries)
        tokenized_metadata = self.tokenize_text(metadata)

        return processed_filepath, tokenized_tags, tokenized_metadata

    def update_entity_index(self, entity_id: int, db: Session):
        """Update both FTS and vector indexes for an entity"""
        try:
            from .crud import get_entity_by_id

            entity = get_entity_by_id(entity_id, db)
            if not entity:
                raise ValueError(f"Entity with id {entity_id} not found")

            # Update FTS index with tokenized data
            processed_filepath, tokenized_tags, tokenized_metadata = (
                self.prepare_fts_data(entity)
            )

            db.execute(
                text(
                    """
                    INSERT INTO entities_fts (id, filepath, tags, metadata)
                    VALUES (:id, :filepath, :tags, :metadata)
                    ON CONFLICT (id) DO UPDATE SET
                        filepath = :filepath,
                        tags = :tags,
                        metadata = :metadata
                    """
                ),
                {
                    "id": entity.id,
                    "filepath": processed_filepath,
                    "tags": tokenized_tags,
                    "metadata": tokenized_metadata,
                },
            )

            # Update vector index
            vec_metadata = self.prepare_vec_data(entity)
            with logfire.span("get embedding for entity metadata"):
                embeddings = get_embeddings([vec_metadata])
                logfire.info(f"vec_metadata: {vec_metadata}")

            if embeddings and embeddings[0]:
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
                created_at_timestamp = int(datetime.now().timestamp())
                file_created_at_timestamp = int(entity.file_created_at.timestamp())
                file_created_at_date = entity.file_created_at.strftime("%Y-%m-%d")

                db.execute(
                    text(
                        """
                        INSERT INTO entities_vec_v2 (
                            rowid, embedding, app_name, file_type_group,
                            created_at_timestamp, file_created_at_timestamp,
                            file_created_at_date, library_id
                        )
                        VALUES (
                            :id, vector(:embedding), :app_name, :file_type_group,
                            :created_at_timestamp, :file_created_at_timestamp,
                            :file_created_at_date, :library_id
                        )
                        ON CONFLICT (rowid) DO UPDATE SET
                            embedding = vector(:embedding),
                            app_name = :app_name,
                            file_type_group = :file_type_group,
                            created_at_timestamp = :created_at_timestamp,
                            file_created_at_timestamp = :file_created_at_timestamp,
                            file_created_at_date = :file_created_at_date,
                            library_id = :library_id
                        """
                    ),
                    {
                        "id": entity.id,
                        "embedding": str(
                            embeddings[0]
                        ),  # Convert to string for PostgreSQL vector type
                        "app_name": app_name,
                        "file_type_group": file_type_group,
                        "created_at_timestamp": created_at_timestamp,
                        "file_created_at_timestamp": file_created_at_timestamp,
                        "file_created_at_date": file_created_at_date,
                        "library_id": entity.library_id,
                    },
                )

            db.commit()
        except Exception as e:
            logger.error(f"Error updating indexes for entity {entity_id}: {e}")
            db.rollback()
            raise

    def batch_update_entity_indices(self, entity_ids: List[int], db: Session):
        """Batch update both FTS and vector indexes for multiple entities"""
        try:
            from sqlalchemy.orm import selectinload
            from .models import EntityModel

            entities = (
                db.query(EntityModel)
                .filter(EntityModel.id.in_(entity_ids))
                .options(
                    selectinload(EntityModel.metadata_entries),
                    selectinload(EntityModel.tags),
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
                    WHERE rowid = ANY(:entity_ids)
                    """
                ),
                {"entity_ids": entity_ids},
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

            logfire.info(
                f"Entities needing full indexing: {len(needs_index)}/{len(entity_ids)}"
            )

            # Update vector index only for entities that need it
            if needs_index:
                vec_metadata_list = [
                    self.prepare_vec_data(entity) for entity in needs_index
                ]
                with logfire.span("get embedding in batch indexing"):
                    embeddings = get_embeddings(vec_metadata_list)
                    logfire.info(f"vec_metadata_list: {vec_metadata_list}")

                # Prepare batch insert data for vector index
                created_at_timestamp = int(datetime.now().timestamp())
                insert_values = []
                for entity, embedding in zip(needs_index, embeddings):
                    if embedding:
                        app_name = next(
                            (
                                entry.value
                                for entry in entity.metadata_entries
                                if entry.key == "active_app"
                            ),
                            "unknown",
                        )
                        file_type_group = entity.file_type_group or "unknown"
                        file_created_at_timestamp = int(
                            entity.file_created_at.timestamp()
                        )
                        file_created_at_date = entity.file_created_at.strftime(
                            "%Y-%m-%d"
                        )

                        insert_values.append(
                            {
                                "id": entity.id,
                                "embedding": str(
                                    embedding
                                ),  # Convert to string for PostgreSQL vector type
                                "app_name": app_name,
                                "file_type_group": file_type_group,
                                "created_at_timestamp": created_at_timestamp,
                                "file_created_at_timestamp": file_created_at_timestamp,
                                "file_created_at_date": file_created_at_date,
                                "library_id": entity.library_id,
                            }
                        )

                # Batch insert/update vector index
                if insert_values:
                    db.execute(
                        text(
                            """
                            INSERT INTO entities_vec_v2 (
                                rowid, embedding, app_name, file_type_group,
                                created_at_timestamp, file_created_at_timestamp,
                                file_created_at_date, library_id
                            )
                            VALUES (
                                :id, vector(:embedding), :app_name, :file_type_group,
                                :created_at_timestamp, :file_created_at_timestamp,
                                :file_created_at_date, :library_id
                            )
                            ON CONFLICT (rowid) DO UPDATE SET
                                embedding = vector(:embedding),
                                app_name = :app_name,
                                file_type_group = :file_type_group,
                                created_at_timestamp = :created_at_timestamp,
                                file_created_at_timestamp = :file_created_at_timestamp,
                                file_created_at_date = :file_created_at_date,
                                library_id = :library_id
                            """
                        ),
                        insert_values,
                    )

            # Update FTS index
            for entity in needs_index:
                processed_filepath, tokenized_tags, tokenized_metadata = (
                    self.prepare_fts_data(entity)
                )

                db.execute(
                    text(
                        """
                        INSERT INTO entities_fts (id, filepath, tags, metadata)
                        VALUES (:id, :filepath, :tags, :metadata)
                        ON CONFLICT (id) DO UPDATE SET
                            filepath = :filepath,
                            tags = :tags,
                            metadata = :metadata
                        """
                    ),
                    {
                        "id": entity.id,
                        "filepath": processed_filepath,
                        "tags": tokenized_tags,
                        "metadata": tokenized_metadata,
                    },
                )

            db.commit()

        except Exception as e:
            logger.error(f"Error batch updating indexes: {e}")
            db.rollback()
            raise

    def full_text_search(
        self,
        query: str,
        db: Session,
        limit: int = 200,
        library_ids: Optional[List[int]] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        app_names: Optional[List[str]] = None,
    ) -> List[int]:
        base_sql = """
        WITH search_results AS (
            SELECT e.id,
                ts_rank_cd(f.search_vector, websearch_to_tsquery('simple', :query)) as rank
            FROM entities_fts f
            JOIN entities e ON e.id = f.id
            WHERE f.search_vector @@ websearch_to_tsquery('simple', :query)
            AND e.file_type_group = 'image'
        """

        where_clauses = []
        if library_ids:
            where_clauses.append("e.library_id = ANY(:library_ids)")

        if start is not None and end is not None:
            where_clauses.append(
                "EXTRACT(EPOCH FROM e.file_created_at) BETWEEN :start AND :end"
            )

        if app_names:
            where_clauses.append(
                """
                EXISTS (
                    SELECT 1 FROM metadata_entries me 
                    WHERE me.entity_id = e.id 
                    AND me.key = 'active_app' 
                    AND me.value = ANY(:app_names)
                )
            """
            )

        if where_clauses:
            base_sql += " AND " + " AND ".join(where_clauses)

        base_sql += ")\nSELECT id FROM search_results ORDER BY rank DESC LIMIT :limit"

        params = {"query": query, "limit": limit}

        if library_ids:
            params["library_ids"] = library_ids

        if start is not None and end is not None:
            params["start"] = start
            params["end"] = end

        if app_names:
            params["app_names"] = app_names

        logfire.info(
            "full text search {query=} {limit=}",
            query=query,
            limit=limit,
        )

        sql = text(base_sql)
        result = db.execute(sql, params).fetchall()
        return [row[0] for row in result]

    def vector_search(
        self,
        embeddings: List[float],
        db: Session,
        limit: int = 200,
        library_ids: Optional[List[int]] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        app_names: Optional[List[str]] = None,
    ) -> List[int]:
        sql_query = """
        SELECT rowid
        FROM entities_vec_v2
        WHERE file_type_group = 'image'
        """

        params = {
            "embedding": str(
                embeddings
            ),  # Convert to string for PostgreSQL vector type
            "limit": limit,
        }

        if library_ids:
            sql_query += " AND library_id = ANY(:library_ids)"
            params["library_ids"] = library_ids

        if start is not None and end is not None:
            sql_query += " AND file_created_at_timestamp BETWEEN :start AND :end"
            params["start"] = start
            params["end"] = end

        if app_names:
            sql_query += " AND app_name = ANY(:app_names)"
            params["app_names"] = app_names

        # Add vector similarity search
        sql_query += """
        ORDER BY embedding <=> vector(:embedding)
        LIMIT :limit
        """

        sql = text(sql_query)
        result = db.execute(sql, params).fetchall()

        return [row[0] for row in result]

    def reciprocal_rank_fusion(
        self, fts_results: List[int], vec_results: List[int], k: int = 60
    ) -> List[Tuple[int, float]]:
        rank_dict = defaultdict(float)

        # Weight for full-text search results: 0.7
        for rank, result_id in enumerate(fts_results):
            rank_dict[result_id] += 0.7 * (1 / (k + rank + 1))

        # Weight for vector search results: 0.3
        for rank, result_id in enumerate(vec_results):
            rank_dict[result_id] += 0.3 * (1 / (k + rank + 1))

        return sorted(rank_dict.items(), key=lambda x: x[1], reverse=True)

    def hybrid_search(
        self,
        query: str,
        db: Session,
        limit: int = 200,
        library_ids: Optional[List[int]] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        app_names: Optional[List[str]] = None,
    ) -> List[int]:
        with logfire.span("full_text_search {query=}", query=query):
            fts_results = self.full_text_search(
                query, db, limit, library_ids, start, end, app_names
            )
        logger.info(f"Full-text search obtained {len(fts_results)} results")

        with logfire.span("vector_search {query=}", query=query):
            embeddings = get_embeddings([query])
            if embeddings and embeddings[0]:
                vec_results = self.vector_search(
                    embeddings[0], db, limit * 2, library_ids, start, end, app_names
                )
                logger.info(f"Vector search obtained {len(vec_results)} results")
            else:
                vec_results = []

        with logfire.span("reciprocal_rank_fusion {query=}", query=query):
            combined_results = self.reciprocal_rank_fusion(fts_results, vec_results)

        sorted_ids = [id for id, _ in combined_results][:limit]
        logger.info(f"Hybrid search results (sorted IDs): {sorted_ids}")

        return sorted_ids

    @logfire.instrument
    def get_search_stats(
        self,
        query: str,
        db: Session,
        library_ids: Optional[List[int]] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        app_names: Optional[List[str]] = None,
    ) -> dict:
        """Get statistics for search results including date range and app name counts."""
        MIN_SAMPLE_SIZE = 1024
        MAX_SAMPLE_SIZE = 2048

        with logfire.span(
            "full_text_search in stats {query=} {limit=}",
            query=query,
            limit=MAX_SAMPLE_SIZE,
        ):
            fts_results = self.full_text_search(
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
            embeddings = get_embeddings([query])
            if embeddings and embeddings[0]:
                vec_results = self.vector_search(
                    embeddings[0],
                    db,
                    limit=vec_limit,
                    library_ids=library_ids,
                    start=start,
                    end=end,
                    app_names=app_names,
                )
            else:
                vec_results = []

        logfire.info(f"fts_results: {len(fts_results)} vec_results: {len(vec_results)}")

        entity_ids = set(fts_results + vec_results)

        if not entity_ids:
            return {
                "date_range": {"earliest": None, "latest": None},
                "app_name_counts": {},
            }

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
            "date_range": {
                "earliest": date_range.earliest,
                "latest": date_range.latest,
            },
            "app_name_counts": {app_name: count for app_name, count in app_name_counts},
        }


class SqliteSearchProvider(SearchProvider):
    def and_words(self, input_string: str) -> str:
        words = input_string.split()
        result = " AND ".join(words)
        return result

    def prepare_fts_data(self, entity) -> tuple[str, str]:
        tags = ", ".join(entity.tag_names)
        fts_metadata = "\n".join(
            [
                f"{entry.key}: {self.process_ocr_result(entry.value) if entry.key == 'ocr_result' else entry.value}"
                for entry in entity.metadata_entries
            ]
        )
        return tags, fts_metadata

    def update_entity_index(self, entity_id: int, db: Session):
        """Update both FTS and vector indexes for an entity"""
        try:
            from .crud import get_entity_by_id

            entity = get_entity_by_id(entity_id, db)
            if not entity:
                raise ValueError(f"Entity with id {entity_id} not found")

            # Update FTS index
            tags, fts_metadata = self.prepare_fts_data(entity)
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
            vec_metadata = self.prepare_vec_data(entity)
            with logfire.span("get embedding for entity metadata"):
                embeddings = get_embeddings([vec_metadata])
                logfire.info(f"vec_metadata: {vec_metadata}")

            if embeddings and embeddings[0]:
                db.execute(
                    text("DELETE FROM entities_vec_v2 WHERE rowid = :id"),
                    {"id": entity.id},
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
                        "file_created_at_date": entity.file_created_at.strftime(
                            "%Y-%m-%d"
                        ),
                        "library_id": entity.library_id,
                    },
                )

            db.commit()
        except Exception as e:
            logger.error(f"Error updating indexes for entity {entity_id}: {e}")
            db.rollback()
            raise

    def batch_update_entity_indices(self, entity_ids: List[int], db: Session):
        """Batch update both FTS and vector indexes for multiple entities"""
        try:
            from sqlalchemy.orm import selectinload
            from .models import EntityModel

            entities = (
                db.query(EntityModel)
                .filter(EntityModel.id.in_(entity_ids))
                .options(
                    selectinload(EntityModel.metadata_entries),
                    selectinload(EntityModel.tags),
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

            logfire.info(
                f"Entities needing full indexing: {len(needs_index)}/{len(entity_ids)}"
            )

            # Handle entities needing full indexing
            if needs_index:
                vec_metadata_list = [
                    self.prepare_vec_data(entity) for entity in needs_index
                ]
                with logfire.span("get embedding in batch indexing"):
                    embeddings = get_embeddings(vec_metadata_list)
                    logfire.info(f"vec_metadata_list: {vec_metadata_list}")

                # Delete all existing vector indices in one query
                if needs_index:
                    db.execute(
                        text(
                            "DELETE FROM entities_vec_v2 WHERE rowid IN :ids"
                        ).bindparams(bindparam("ids", expanding=True)),
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
                tags, fts_metadata = self.prepare_fts_data(entity)
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

    def full_text_search(
        self,
        query: str,
        db: Session,
        limit: int = 200,
        library_ids: Optional[List[int]] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        app_names: Optional[List[str]] = None,
    ) -> List[int]:
        start_time = time.time()

        and_query = self.and_words(query)

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
        bindparams = []

        if library_ids:
            sql_query += " AND e.library_id IN :library_ids"
            params["library_ids"] = tuple(library_ids)
            bindparams.append(bindparam("library_ids", expanding=True))

        if start is not None and end is not None:
            sql_query += (
                " AND strftime('%s', e.file_created_at, 'utc') BETWEEN :start AND :end"
            )
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

        sql = text(sql_query)
        if bindparams:
            sql = sql.bindparams(*bindparams)

        result = db.execute(sql, params).fetchall()

        execution_time = time.time() - start_time
        logger.info(f"Full-text search execution time: {execution_time:.4f} seconds")

        return [row[0] for row in result]

    def vector_search(
        self,
        embeddings: List[float],
        db: Session,
        limit: int = 200,
        library_ids: Optional[List[int]] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        app_names: Optional[List[str]] = None,
    ) -> List[int]:
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
            "embedding": serialize_float32(embeddings),
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

        sql = text(sql_query)
        if app_names:
            sql = sql.bindparams(bindparam("app_names", expanding=True))
        if library_ids:
            sql = sql.bindparams(bindparam("library_ids", expanding=True))

        with logfire.span("vec_search"):
            result = db.execute(sql, params).fetchall()

        return [row[0] for row in result]

    def reciprocal_rank_fusion(
        self, fts_results: List[int], vec_results: List[int], k: int = 60
    ) -> List[Tuple[int, float]]:
        rank_dict = defaultdict(float)

        # Weight for full-text search results: 0.7
        for rank, result_id in enumerate(fts_results):
            rank_dict[result_id] += 0.7 * (1 / (k + rank + 1))

        # Weight for vector search results: 0.3
        for rank, result_id in enumerate(vec_results):
            rank_dict[result_id] += 0.3 * (1 / (k + rank + 1))

        return sorted(rank_dict.items(), key=lambda x: x[1], reverse=True)

    def hybrid_search(
        self,
        query: str,
        db: Session,
        limit: int = 200,
        library_ids: Optional[List[int]] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        app_names: Optional[List[str]] = None,
    ) -> List[int]:
        with logfire.span("full_text_search"):
            fts_results = self.full_text_search(
                query, db, limit, library_ids, start, end, app_names
            )
        logger.info(f"Full-text search obtained {len(fts_results)} results")

        with logfire.span("vector_search"):
            embeddings = get_embeddings([query])
            if embeddings and embeddings[0]:
                vec_results = self.vector_search(
                    embeddings[0], db, limit * 2, library_ids, start, end, app_names
                )
                logger.info(f"Vector search obtained {len(vec_results)} results")
            else:
                vec_results = []

        with logfire.span("reciprocal_rank_fusion"):
            combined_results = self.reciprocal_rank_fusion(fts_results, vec_results)

        sorted_ids = [id for id, _ in combined_results][:limit]
        logger.info(f"Hybrid search results (sorted IDs): {sorted_ids}")

        return sorted_ids

    @logfire.instrument
    def get_search_stats(
        self,
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
            fts_results = self.full_text_search(
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
            embeddings = get_embeddings([query])
            if embeddings and embeddings[0]:
                vec_results = self.vector_search(
                    embeddings[0],
                    db,
                    limit=vec_limit,
                    library_ids=library_ids,
                    start=start,
                    end=end,
                    app_names=app_names,
                )
            else:
                vec_results = []

        logfire.info(f"fts_results: {len(fts_results)} vec_results: {len(vec_results)}")

        entity_ids = set(fts_results + vec_results)

        if not entity_ids:
            return {
                "date_range": {"earliest": None, "latest": None},
                "app_name_counts": {},
            }

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
            "date_range": {
                "earliest": date_range.earliest,
                "latest": date_range.latest,
            },
            "app_name_counts": {app_name: count for app_name, count in app_name_counts},
        }


def create_search_provider(database_url: str) -> SearchProvider:
    """
    Factory function to create appropriate SearchProvider based on database URL.

    Args:
        database_url: Database connection URL

    Returns:
        SearchProvider: Appropriate search provider instance
    """
    if database_url.startswith("postgresql://"):
        logger.info("Using PostgreSQL search provider")
        return PostgreSQLSearchProvider()
    else:
        logger.info("Using SQLite search provider")
        return SqliteSearchProvider()
