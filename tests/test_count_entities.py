"""Test crud.count_entities — used when /api/search receives empty q."""
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from memos.models import Base, EntityModel
from memos import crud


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _add_entity(db, *, library_id, file_type_group="image", file_created_at=None):
    e = EntityModel(
        filepath=f"/fake/{id(file_created_at)}-{library_id}-{file_type_group}.webp",
        filename="x.webp",
        size=1,
        file_created_at=file_created_at or datetime(2026, 5, 1, tzinfo=timezone.utc),
        file_last_modified_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        file_type="webp",
        file_type_group=file_type_group,
        library_id=library_id,
        folder_id=1,
    )
    db.add(e)
    db.commit()
    return e


def test_count_entities_empty_db_is_zero():
    db = _make_session()
    assert crud.count_entities(db=db) == 0


def test_count_entities_only_counts_image_group():
    db = _make_session()
    _add_entity(db, library_id=1, file_type_group="image")
    _add_entity(db, library_id=1, file_type_group="document")
    assert crud.count_entities(db=db) == 1


def test_count_entities_filters_by_library():
    db = _make_session()
    _add_entity(db, library_id=1)
    _add_entity(db, library_id=2)
    assert crud.count_entities(db=db, library_ids=[1]) == 1
    assert crud.count_entities(db=db, library_ids=[1, 2]) == 2


def test_count_entities_filters_by_time_window():
    db = _make_session()
    _add_entity(db, library_id=1, file_created_at=datetime(2026, 4, 1, tzinfo=timezone.utc))
    _add_entity(db, library_id=1, file_created_at=datetime(2026, 5, 1, tzinfo=timezone.utc))
    apr_30 = int(datetime(2026, 4, 30, tzinfo=timezone.utc).timestamp())
    may_2 = int(datetime(2026, 5, 2, tzinfo=timezone.utc).timestamp())
    assert crud.count_entities(db=db, start=apr_30, end=may_2) == 1
