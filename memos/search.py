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


class PostgreSQLSearchProvider(SearchProvider):
    """
    PostgreSQL implementation of SearchProvider.
    This is currently a placeholder with fake implementations.
    TODO: Implement actual PostgreSQL search functionality.
    """

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
        logger.info(
            "PostgreSQL full text search (placeholder) called with query: %s", query
        )
        # Return empty list as placeholder
        return []

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
        logger.info("PostgreSQL vector search (placeholder) called")
        # Return empty list as placeholder
        return []

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
        logger.info(
            "PostgreSQL hybrid search (placeholder) called with query: %s", query
        )
        # Return empty list as placeholder
        return []

    def get_search_stats(
        self,
        query: str,
        db: Session,
        library_ids: Optional[List[int]] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        app_names: Optional[List[str]] = None,
    ) -> dict:
        logger.info(
            "PostgreSQL get_search_stats (placeholder) called with query: %s", query
        )
        return {"date_range": {"earliest": None, "latest": None}, "app_name_counts": {}}


class SqliteSearchProvider(SearchProvider):
    def and_words(self, input_string: str) -> str:
        words = input_string.split()
        result = " AND ".join(words)
        return result

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
