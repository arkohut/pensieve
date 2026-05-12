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


def _adaptive_bucket_unit(earliest, latest, threshold_days: int = 60) -> Optional[str]:
    """Pick 'day' if the [earliest, latest] span is <= threshold_days, else 'month'.
    Returns None when the span can't be derived.
    """
    if earliest is None or latest is None:
        return None

    def _to_dt(v):
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace(" ", "T"))
            except ValueError:
                return None
        return None

    e, l = _to_dt(earliest), _to_dt(latest)
    if e is None or l is None:
        return None
    return "day" if (l - e).total_seconds() / 86400 <= threshold_days else "month"


COUNT_CAP = 5000  # Stop counting beyond this; UI renders "{COUNT_CAP}+".


def _time_window_clauses(
    column_sql: str, start: Optional[int], end: Optional[int], params: dict
) -> List[str]:
    """Build WHERE clauses for an optional time window and add the matching
    bind parameters in-place.

    Each bound is independent — a half-open window (start only or end only)
    applies just that side. The previous `start AND end` gating silently
    dropped the filter when one bound was missing (e.g. the user picked a
    'from' date but no 'to' in the custom date picker), making the query
    scan the whole index.
    """
    clauses: List[str] = []
    if start is not None:
        clauses.append(f"{column_sql} >= :start")
        params["start"] = start
    if end is not None:
        clauses.append(f"{column_sql} <= :end")
        params["end"] = end
    return clauses
# Cap for FTS rank scoring. ts_rank_cd is computed per match before sorting;
# capping early lets PostgreSQL stop scanning once enough matches are
# collected. RRF still pairs this with vector search top-K so the final
# hybrid ranking remains relevance-driven even when FTS is approximate.
FTS_RANK_CAP = 5000


def _assemble_stats(rows) -> dict:
    """Fold the kind-tagged UNION ALL rows from get_search_stats SQL into the
    public stats dict (date_range, app_name_counts, date_buckets, bucket_unit).

    Both PG and SQLite providers emit the same 'range'|'day'|'month'|'app'
    row shape, so this assembly is shared.
    """
    earliest = latest = None
    total = 0
    day_rows: List[Tuple[str, int]] = []
    month_rows: List[Tuple[str, int]] = []
    app_counts: dict = {}

    for r in rows:
        if r.kind == "range":
            earliest, latest, total = r.earliest, r.latest, r.count
        elif r.kind == "day":
            day_rows.append((r.label, r.count))
        elif r.kind == "month":
            month_rows.append((r.label, r.count))
        elif r.kind == "app":
            app_counts[r.label] = r.count

    if not total:
        return {
            "date_range": {"earliest": None, "latest": None},
            "app_name_counts": {},
            "date_buckets": [],
            "bucket_unit": None,
            "total": 0,
        }

    bucket_unit = _adaptive_bucket_unit(earliest, latest)
    chosen = day_rows if bucket_unit == "day" else month_rows
    # Suppress degenerate single-bucket facets — they offer no filtering value.
    if len(chosen) > 1:
        chosen.sort(key=lambda x: x[0], reverse=True)
        date_buckets = [{"date": d, "count": c} for d, c in chosen]
    else:
        date_buckets = []
        bucket_unit = None

    sorted_apps = dict(sorted(app_counts.items(), key=lambda kv: -kv[1]))

    return {
        "date_range": {"earliest": earliest, "latest": latest},
        "app_name_counts": sorted_apps,
        "date_buckets": date_buckets,
        "bucket_unit": bucket_unit,
        "total": total,
    }


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

    @abstractmethod
    def count_full_text_matches(
        self,
        query: str,
        db: Session,
        library_ids: Optional[List[int]] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        app_names: Optional[List[str]] = None,
    ) -> int:
        """Return the total number of full-text matches under the given filters,
        unbounded by limit. Used to populate SearchResult.found honestly."""
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

            entity = get_entity_by_id(entity_id, db, include_relationships=True)
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

    def _build_fts_filters(
        self,
        query: str,
        library_ids: Optional[List[int]],
        start: Optional[int],
        end: Optional[int],
        app_names: Optional[List[str]],
    ) -> Tuple[List[str], dict, list]:
        """Shared WHERE-clause and bind-param assembly for FTS queries.

        Returns `(where_clauses, params, bindparams)`. `bindparams` is always
        empty on PG (native array binding via `= ANY(:...)`); the slot is
        kept for symmetry with the SQLite provider, whose IN-list filters
        need `bindparam("...", expanding=True)`.

        `params["query"]` is pre-tokenized with jieba so a Chinese phrase
        matches the same tokens the index was built from. The 'simple'
        tsvector tokenizer can't segment CJK runs on its own.
        """
        params: dict = {"query": self.tokenize_text(query)}
        where_clauses: List[str] = ["e.file_type_group = 'image'"]
        if library_ids:
            where_clauses.append("e.library_id = ANY(:library_ids)")
            params["library_ids"] = library_ids
        where_clauses.extend(
            _time_window_clauses(
                "EXTRACT(EPOCH FROM e.file_created_at)", start, end, params
            )
        )
        if app_names:
            where_clauses.append(
                "EXISTS ("
                "SELECT 1 FROM metadata_entries me "
                "WHERE me.entity_id = e.id "
                "AND me.key = 'active_app' "
                "AND me.value = ANY(:app_names))"
            )
            params["app_names"] = app_names
        return where_clauses, params, []

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
        # Inner CTE scans FTS + filters up to FTS_RANK_CAP rows, computing
        # ts_rank_cd for each. The outer query sorts that capped subset and
        # returns the top :limit. For high-frequency keywords this avoids
        # ranking the full match set (10k+ rows); for rare ones the LIMIT is
        # never reached and behavior is identical.
        where_clauses, params, _ = self._build_fts_filters(
            query, library_ids, start, end, app_names
        )
        params["limit"] = limit
        params["rank_cap"] = FTS_RANK_CAP
        sql = text(
            f"""
        WITH search_results AS (
            SELECT e.id,
                ts_rank_cd(f.search_vector, websearch_to_tsquery('simple', :query)) as rank
            FROM entities_fts f
            JOIN entities e ON e.id = f.id
            WHERE f.search_vector @@ websearch_to_tsquery('simple', :query)
            AND {" AND ".join(where_clauses)}
            LIMIT :rank_cap
        )
        SELECT id FROM search_results ORDER BY rank DESC LIMIT :limit
        """
        )

        logfire.info(
            "full text search {query=} {limit=}",
            query=query,
            limit=limit,
        )

        result = db.execute(sql, params).fetchall()
        return [row[0] for row in result]

    def count_full_text_matches(
        self,
        query: str,
        db: Session,
        library_ids: Optional[List[int]] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        app_names: Optional[List[str]] = None,
    ) -> int:
        # Cap the inner scan so very broad queries (155k+ matches) don't pay
        # the full COUNT cost. UI surfaces COUNT_CAP+ as "{COUNT_CAP}+".
        where_clauses, params, _ = self._build_fts_filters(
            query, library_ids, start, end, app_names
        )
        params["cap"] = COUNT_CAP + 1
        sql = text(
            f"""
        SELECT COUNT(*) FROM (
            SELECT 1
            FROM entities_fts f
            JOIN entities e ON e.id = f.id
            WHERE f.search_vector @@ websearch_to_tsquery('simple', :query)
            AND {" AND ".join(where_clauses)}
            LIMIT :cap
        ) sub
        """
        )
        result = db.execute(sql, params).scalar()
        return int(result or 0)

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

        for clause in _time_window_clauses(
            "file_created_at_timestamp", start, end, params
        ):
            sql_query += f" AND {clause}"

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
        phase_ms: Optional[dict] = None,
    ) -> List[int]:
        def _measure(name: str, fn):
            if phase_ms is None:
                return fn()
            t0 = time.perf_counter()
            try:
                return fn()
            finally:
                phase_ms[name] = round((time.perf_counter() - t0) * 1000)

        with logfire.span("full_text_search {query=}", query=query):
            fts_results = _measure(
                "fts",
                lambda: self.full_text_search(
                    query, db, limit, library_ids, start, end, app_names
                ),
            )
        logger.info(f"Full-text search obtained {len(fts_results)} results")

        with logfire.span("vector_search {query=}", query=query):
            embeddings = _measure("embed", lambda: get_embeddings([query]))
            if embeddings and embeddings[0]:
                vec_results = _measure(
                    "vec",
                    lambda: self.vector_search(
                        embeddings[0], db, limit * 2, library_ids, start, end, app_names
                    ),
                )
                logger.info(f"Vector search obtained {len(vec_results)} results")
            else:
                vec_results = []

        with logfire.span("reciprocal_rank_fusion {query=}", query=query):
            combined_results = _measure(
                "rrf", lambda: self.reciprocal_rank_fusion(fts_results, vec_results)
            )

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
        """Get FTS-only statistics: date range, app counts, date buckets.

        Aggregates over the *full* FTS-matched set (no sampling) so bucket
        counts match what the user gets when drilling — same semantics as
        `count_full_text_matches`. A single MATERIALIZED CTE keeps this to one
        FTS scan; day and month buckets are both computed and the unit picked
        in Python.

        Vector neighbors are intentionally excluded here so facet counts match
        the keyword-match semantics of `found`.

        Stats must aggregate over the *full* FTS-matched set: facets are the
        user's map of what's behind their search ("4500 in iTerm2, 800 in
        Chrome..."), and a sample makes that map lie — the next drill into
        iTerm2 would surface more than the facet count promised, and rare
        apps falling outside the sample would simply not appear as options
        the user can pick. See 3a6b335 for the same lesson.
        """
        where_clauses, params, _ = self._build_fts_filters(
            query, library_ids, start, end, app_names
        )
        sql = f"""
        WITH fts_matches AS MATERIALIZED (
            SELECT e.id, e.file_created_at
            FROM entities_fts f
            JOIN entities e ON e.id = f.id
            WHERE f.search_vector @@ websearch_to_tsquery('simple', :query)
            AND {" AND ".join(where_clauses)}
        )
        SELECT 'range'::text AS kind, NULL::text AS label,
               MIN(file_created_at)::timestamp AS earliest,
               MAX(file_created_at)::timestamp AS latest,
               COUNT(*)::bigint AS count
        FROM fts_matches
        UNION ALL
        SELECT 'day'::text, to_char(file_created_at, 'YYYY-MM-DD'),
               NULL::timestamp, NULL::timestamp, COUNT(*)::bigint
        FROM fts_matches
        GROUP BY to_char(file_created_at, 'YYYY-MM-DD')
        UNION ALL
        SELECT 'month'::text, to_char(file_created_at, 'YYYY-MM'),
               NULL::timestamp, NULL::timestamp, COUNT(*)::bigint
        FROM fts_matches
        GROUP BY to_char(file_created_at, 'YYYY-MM')
        UNION ALL
        SELECT 'app'::text, me.value,
               NULL::timestamp, NULL::timestamp, COUNT(*)::bigint
        FROM fts_matches fm
        JOIN metadata_entries me ON me.entity_id = fm.id
        WHERE me.key = 'active_app'
        GROUP BY me.value
        """

        with logfire.span("fts_stats_aggregation {query=}", query=query):
            rows = db.execute(text(sql), params).all()

        return _assemble_stats(rows)


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

            entity = get_entity_by_id(entity_id, db, include_relationships=True)
            if not entity:
                raise ValueError(f"Entity with id {entity_id} not found")

            # Update FTS index
            tags, fts_metadata = self.prepare_fts_data(entity)
            db.execute(
                text("DELETE FROM entities_fts WHERE id = :id"),
                {"id": entity.id},
            )
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
            db.execute(
                text("DELETE FROM entities_fts WHERE id IN :ids").bindparams(
                    bindparam("ids", expanding=True)
                ),
                {"ids": tuple(entity.id for entity in entities)},
            )
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

    def _build_fts_filters(
        self,
        query: str,
        library_ids: Optional[List[int]],
        start: Optional[int],
        end: Optional[int],
        app_names: Optional[List[str]],
    ) -> Tuple[List[str], dict, list]:
        """Sister to the PG helper — same shape, dialect-specific SQL.

        Returns `(where_clauses, params, bindparams)`. SQLite's IN-list
        filters need `bindparam(..., expanding=True)` to expand tuples; the
        list collects those so callers can attach them to the bound `text()`.

        `params["query"]` is and_words-joined; the jieba segmentation itself
        runs inside SQLite via the `jieba_query(:query)` extension.
        """
        params: dict = {"query": self.and_words(query)}
        where_clauses: List[str] = ["e.file_type_group = 'image'"]
        bindparams: list = []
        if library_ids:
            where_clauses.append("e.library_id IN :library_ids")
            params["library_ids"] = tuple(library_ids)
            bindparams.append(bindparam("library_ids", expanding=True))
        where_clauses.extend(
            _time_window_clauses(
                "strftime('%s', e.file_created_at, 'utc')", start, end, params
            )
        )
        if app_names:
            where_clauses.append(
                "EXISTS ("
                "SELECT 1 FROM metadata_entries me "
                "WHERE me.entity_id = e.id "
                "AND me.key = 'active_app' "
                "AND me.value IN :app_names)"
            )
            params["app_names"] = tuple(app_names)
            bindparams.append(bindparam("app_names", expanding=True))
        return where_clauses, params, bindparams

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

        where_clauses, params, bindparams = self._build_fts_filters(
            query, library_ids, start, end, app_names
        )
        params["limit"] = limit
        sql = text(
            f"""
        WITH fts_matches AS (
            SELECT id, rank
            FROM entities_fts
            WHERE entities_fts MATCH jieba_query(:query)
        )
        SELECT e.id
        FROM fts_matches f
        JOIN entities e ON e.id = f.id
        WHERE {" AND ".join(where_clauses)}
        ORDER BY f.rank LIMIT :limit
        """
        )
        if bindparams:
            sql = sql.bindparams(*bindparams)

        result = db.execute(sql, params).fetchall()

        execution_time = time.time() - start_time
        logger.info(f"Full-text search execution time: {execution_time:.4f} seconds")

        return [row[0] for row in result]

    def count_full_text_matches(
        self,
        query: str,
        db: Session,
        library_ids: Optional[List[int]] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        app_names: Optional[List[str]] = None,
    ) -> int:
        # Cap the inner FTS scan so very broad queries don't pay the full
        # COUNT cost. UI surfaces COUNT_CAP+ as "{COUNT_CAP}+".
        where_clauses, params, bindparams = self._build_fts_filters(
            query, library_ids, start, end, app_names
        )
        params["cap"] = COUNT_CAP + 1
        sql = text(
            f"""
        SELECT COUNT(*) FROM (
            WITH fts_matches AS (
                SELECT id
                FROM entities_fts
                WHERE entities_fts MATCH jieba_query(:query)
            )
            SELECT 1
            FROM fts_matches f
            JOIN entities e ON e.id = f.id
            WHERE {" AND ".join(where_clauses)}
            LIMIT :cap
        ) sub
        """
        )
        if bindparams:
            sql = sql.bindparams(*bindparams)

        result = db.execute(sql, params).scalar()
        return int(result or 0)

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
        start_date = (
            datetime.fromtimestamp(start).strftime("%Y-%m-%d")
            if start is not None
            else None
        )
        end_date = (
            datetime.fromtimestamp(end).strftime("%Y-%m-%d")
            if end is not None
            else None
        )

        sql_query = f"""
        SELECT rowid
        FROM entities_vec_v2
        WHERE embedding MATCH :embedding
          AND file_type_group = 'image'
          AND K = :limit
          {"AND file_created_at_date >= :start_date" if start_date is not None else ""}
          {"AND file_created_at_date <= :end_date" if end_date is not None else ""}
          {"AND file_created_at_timestamp >= :start" if start is not None else ""}
          {"AND file_created_at_timestamp <= :end" if end is not None else ""}
          {"AND library_id IN :library_ids" if library_ids else ""}
          {"AND app_name IN :app_names" if app_names else ""}
        ORDER BY distance ASC
        """

        params = {
            "embedding": serialize_float32(embeddings),
            "limit": limit,
        }

        if start is not None:
            params["start"] = int(start)
            params["start_date"] = start_date
        if end is not None:
            params["end"] = int(end)
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
        """Get FTS-only statistics: date range, app counts, date buckets.

        Aggregates over the *full* FTS-matched set (no sampling) so bucket
        counts match what the user gets when drilling — same semantics as
        `count_full_text_matches`. A single MATERIALIZED CTE keeps this to one
        FTS scan; day and month buckets are both computed and the unit picked
        in Python.

        Vector neighbors are intentionally excluded here so facet counts match
        the keyword-match semantics of `found`.

        See PG provider above: facets must reflect the full FTS-matched set
        or they mislead the user into picking options the search will then
        exceed (or hide rare options entirely).
        """
        where_clauses, params, bindparams = self._build_fts_filters(
            query, library_ids, start, end, app_names
        )
        sql_str = f"""
        WITH fts_matches AS MATERIALIZED (
            SELECT e.id, e.file_created_at
            FROM entities_fts f
            JOIN entities e ON e.id = f.id
            WHERE entities_fts MATCH jieba_query(:query)
            AND {" AND ".join(where_clauses)}
        )
        SELECT 'range' AS kind, NULL AS label,
               MIN(file_created_at) AS earliest,
               MAX(file_created_at) AS latest,
               COUNT(*) AS count
        FROM fts_matches
        UNION ALL
        SELECT 'day', DATE(file_created_at), NULL, NULL, COUNT(*)
        FROM fts_matches
        GROUP BY DATE(file_created_at)
        UNION ALL
        SELECT 'month', strftime('%Y-%m', file_created_at), NULL, NULL, COUNT(*)
        FROM fts_matches
        GROUP BY strftime('%Y-%m', file_created_at)
        UNION ALL
        SELECT 'app', me.value, NULL, NULL, COUNT(*)
        FROM fts_matches fm
        JOIN metadata_entries me ON me.entity_id = fm.id
        WHERE me.key = 'active_app'
        GROUP BY me.value
        """

        sql = text(sql_str)
        if bindparams:
            sql = sql.bindparams(*bindparams)

        with logfire.span("fts_stats_aggregation {query=}", query=query):
            rows = db.execute(sql, params).all()

        return _assemble_stats(rows)


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
