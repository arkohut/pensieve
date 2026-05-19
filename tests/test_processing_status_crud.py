"""Tests for the processing-status crud helpers."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from memos import crud
from memos.models import (
    Base,
    EntityModel,
    EntityPluginStatusModel,
    FolderModel,
    LibraryModel,
    LibraryPluginModel,
    PluginModel,
)
from memos.schemas import LibraryKind, FolderType


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


def _utc(now_offset_minutes: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=now_offset_minutes)


def _seed(session, *, library_kind=LibraryKind.RECORD, n_plugins=2, entity_specs=()):
    """Seed one library with `n_plugins` bound plugins and entities with the
    plugin-status pattern specified by entity_specs.

    Each entity_spec is a tuple (created_minutes_ago, plugins_done_count).
    Returns (library_id, [entity_ids]).
    """
    lib = LibraryModel(name="test", kind=library_kind)
    session.add(lib)
    session.flush()
    folder = FolderModel(
        library_id=lib.id,
        path="/tmp",
        type=FolderType.DEFAULT,
        last_modified_at=datetime.now(timezone.utc),
    )
    session.add(folder)
    session.flush()
    plugins = []
    for i in range(n_plugins):
        p = PluginModel(name=f"plugin-{i}", webhook_url=f"/p{i}")
        session.add(p)
        session.flush()
        session.add(LibraryPluginModel(library_id=lib.id, plugin_id=p.id))
        plugins.append(p)
    session.flush()
    entity_ids = []
    for created_minutes_ago, plugins_done in entity_specs:
        created_at = _utc(-created_minutes_ago)
        ent = EntityModel(
            filepath=f"/tmp/e-{created_minutes_ago}-{plugins_done}.png",
            filename=f"e-{created_minutes_ago}-{plugins_done}.png",
            size=1,
            file_created_at=created_at,
            file_last_modified_at=created_at,
            file_type="image/png",
            file_type_group="image",
            library_id=lib.id,
            folder_id=folder.id,
            created_at=created_at,
            updated_at=created_at,
            last_scan_at=created_at,
        )
        session.add(ent)
        session.flush()
        for p in plugins[:plugins_done]:
            session.add(
                EntityPluginStatusModel(entity_id=ent.id, plugin_id=p.id)
            )
        entity_ids.append(ent.id)
    session.commit()
    return lib.id, entity_ids


def test_count_entities_in_window_counts_inside_window_only(session):
    # window = 60 minutes; seed 3 inside, 2 outside
    lib_id, _ = _seed(
        session,
        entity_specs=[
            (5, 2),   # 5 min ago, in
            (30, 0),  # 30 min ago, in
            (45, 1),  # 45 min ago, in
            (90, 2),  # 90 min ago, OUT
            (120, 0), # 120 min ago, OUT
        ],
    )
    n = crud.count_entities_in_window(lib_id, window_hours=1, db=session)
    assert n == 3


def test_count_entities_in_window_empty_returns_zero(session):
    lib_id, _ = _seed(session, entity_specs=[])
    assert crud.count_entities_in_window(lib_id, window_hours=24, db=session) == 0


def test_count_fully_processed_only_counts_all_plugins_done(session):
    # 2 plugins. Seed entities where:
    # - inside window, all plugins done → counts
    # - inside window, 1/2 plugins → does NOT count
    # - inside window, 0/2 plugins → does NOT count
    # - outside window, all plugins done → does NOT count
    lib_id, _ = _seed(
        session,
        n_plugins=2,
        entity_specs=[
            (5, 2),   # in, fully processed
            (10, 1),  # in, partial
            (20, 0),  # in, none
            (30, 2),  # in, fully processed
            (90, 2),  # OUT
        ],
    )
    n = crud.count_entities_fully_processed_in_window(lib_id, window_hours=1, db=session)
    assert n == 2


def test_count_fully_processed_returns_zero_when_no_plugins_bound(session):
    # Edge: library has 0 plugins bound. Every entity is trivially "fully
    # processed" (0/0), and we return 0 to avoid divide-by-zero confusion
    # downstream.
    lib_id, _ = _seed(
        session,
        n_plugins=0,
        entity_specs=[(5, 0), (10, 0)],
    )
    assert crud.count_entities_fully_processed_in_window(lib_id, window_hours=1, db=session) == 0


def test_count_unprocessed_counts_anything_missing_plugins(session):
    lib_id, _ = _seed(
        session,
        n_plugins=3,
        entity_specs=[
            (1, 3),    # fully
            (5, 2),    # missing 1
            (10, 0),   # missing all
            (60, 3),   # fully (old)
            (120, 1),  # missing 2 (old)
        ],
    )
    # 5 total, 2 fully processed → 3 unprocessed (regardless of window)
    assert crud.count_unprocessed(lib_id, db=session) == 3


def test_count_unprocessed_zero_plugins_returns_zero(session):
    lib_id, _ = _seed(session, n_plugins=0, entity_specs=[(1, 0), (5, 0)])
    assert crud.count_unprocessed(lib_id, db=session) == 0


def test_oldest_unprocessed_returns_min_created_at(session):
    lib_id, _ = _seed(
        session,
        n_plugins=2,
        entity_specs=[
            (5, 2),     # fully, ignored
            (30, 1),    # unprocessed
            (60, 0),    # unprocessed and older
            (10, 2),    # fully, ignored
        ],
    )
    oldest = crud.get_oldest_unprocessed_created_at(lib_id, db=session)
    # The oldest unprocessed was 60 minutes ago. Allow 5 second jitter.
    # SQLite stores datetimes without timezone, so strip tzinfo from now.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    age = (now - oldest).total_seconds()
    assert 60 * 60 - 5 <= age <= 60 * 60 + 5


def test_oldest_unprocessed_returns_none_when_all_processed(session):
    lib_id, _ = _seed(
        session,
        n_plugins=2,
        entity_specs=[(1, 2), (10, 2)],
    )
    assert crud.get_oldest_unprocessed_created_at(lib_id, db=session) is None


def test_oldest_unprocessed_returns_none_when_no_plugins_bound(session):
    lib_id, _ = _seed(session, n_plugins=0, entity_specs=[(1, 0), (10, 0)])
    assert crud.get_oldest_unprocessed_created_at(lib_id, db=session) is None
