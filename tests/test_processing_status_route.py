"""Integration tests for GET /api/libraries/{id}/processing-status."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from memos.models import (
    Base,
    EntityModel,
    EntityPluginStatusModel,
    FolderModel,
    LibraryModel,
    LibraryPluginModel,
    PluginModel,
)
from memos.schemas import FolderType, LibraryKind
from memos.server import api_router, app, get_db


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
def client(engine):
    from memos import server as _server

    SessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    api_router.dependency_overrides[get_db] = override_get_db
    _server._processing_status_cache.clear()
    try:
        yield TestClient(app)
    finally:
        api_router.dependency_overrides.pop(get_db, None)
        _server._processing_status_cache.clear()


def _seed_record_lib(engine, *, n_plugins=2, entity_specs=()):
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as db:
        lib = LibraryModel(name="shots", kind=LibraryKind.RECORD)
        db.add(lib)
        db.flush()
        folder = FolderModel(
            library_id=lib.id,
            path="/tmp",
            type=FolderType.DEFAULT,
            last_modified_at=datetime.now(timezone.utc),
        )
        db.add(folder)
        db.flush()
        plugins = []
        for i in range(n_plugins):
            p = PluginModel(name=f"plugin-{i}", webhook_url=f"/p{i}")
            db.add(p)
            db.flush()
            db.add(LibraryPluginModel(library_id=lib.id, plugin_id=p.id))
            plugins.append(p)
        for created_minutes_ago, plugins_done in entity_specs:
            created_at = datetime.now(timezone.utc) - timedelta(minutes=created_minutes_ago)
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
            db.add(ent)
            db.flush()
            for p in plugins[:plugins_done]:
                db.add(EntityPluginStatusModel(entity_id=ent.id, plugin_id=p.id))
        db.commit()
        return lib.id


def _seed_static_lib(engine):
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as db:
        lib = LibraryModel(name="imports", kind=LibraryKind.STATIC)
        db.add(lib)
        db.commit()
        return lib.id


def test_returns_200_for_record_library(client, engine, monkeypatch):
    # Pin the watch predicates to a known-good "running fine" state.
    monkeypatch.setattr("memos.utils.watch_state.is_alive", lambda: True)
    monkeypatch.setattr("memos.utils.watch_state.is_on_battery", lambda: False)
    monkeypatch.setattr("memos.utils.watch_state.is_within_idle_window", lambda *a, **kw: True)

    lib_id = _seed_record_lib(
        engine,
        n_plugins=2,
        entity_specs=[(5, 2), (10, 1), (20, 0), (90, 2)],
    )

    res = client.get(f"/api/libraries/{lib_id}/processing-status")
    assert res.status_code == 200
    body = res.json()

    assert body["library_id"] == lib_id
    assert body["window_hours"] == 24
    cov = body["coverage_window"]
    # All 4 are in the 24h window. 1 fully processed, 2 unprocessed, 1 fully processed (90 min ago is still in 24h).
    assert cov["total"] == 4
    assert cov["fully_processed"] == 2
    assert abs(cov["pct"] - 0.5) < 1e-6

    bk = body["backlog"]
    assert bk["total_unprocessed"] == 2
    # Oldest is the 20-min-ago one (the 10-min and 20-min ones are unprocessed; 90-min is fully).
    assert 20 * 60 - 5 <= bk["oldest_age_seconds"] <= 20 * 60 + 5

    w = body["watch"]
    assert w["is_alive"] is True
    assert w["is_on_battery"] is False
    assert w["is_within_idle_window"] is True
    assert isinstance(w["idle_window"], list) and len(w["idle_window"]) == 2


def test_returns_404_for_unknown_library(client):
    res = client.get("/api/libraries/9999/processing-status")
    assert res.status_code == 404


def test_returns_400_for_static_library(client, engine):
    lib_id = _seed_static_lib(engine)
    res = client.get(f"/api/libraries/{lib_id}/processing-status")
    assert res.status_code == 400


def test_clamps_window_hours(client, engine, monkeypatch):
    monkeypatch.setattr("memos.utils.watch_state.is_alive", lambda: True)
    monkeypatch.setattr("memos.utils.watch_state.is_on_battery", lambda: False)
    monkeypatch.setattr("memos.utils.watch_state.is_within_idle_window", lambda *a, **kw: True)
    lib_id = _seed_record_lib(engine, n_plugins=1, entity_specs=[])
    # FastAPI Query(ge=1, le=168) should produce 422 on out-of-range values.
    assert client.get(f"/api/libraries/{lib_id}/processing-status?window_hours=0").status_code == 422
    assert client.get(f"/api/libraries/{lib_id}/processing-status?window_hours=169").status_code == 422
    assert client.get(f"/api/libraries/{lib_id}/processing-status?window_hours=24").status_code == 200


def test_empty_window_returns_pct_one_and_null_oldest(client, engine, monkeypatch):
    monkeypatch.setattr("memos.utils.watch_state.is_alive", lambda: True)
    monkeypatch.setattr("memos.utils.watch_state.is_on_battery", lambda: False)
    monkeypatch.setattr("memos.utils.watch_state.is_within_idle_window", lambda *a, **kw: True)
    lib_id = _seed_record_lib(engine, n_plugins=2, entity_specs=[])
    body = client.get(f"/api/libraries/{lib_id}/processing-status").json()
    assert body["coverage_window"]["total"] == 0
    assert body["coverage_window"]["fully_processed"] == 0
    assert body["coverage_window"]["pct"] == 1.0
    assert body["backlog"]["total_unprocessed"] == 0
    assert body["backlog"]["oldest_age_seconds"] is None


def test_cache_skips_db_within_ttl(client, engine, monkeypatch):
    """Two calls within the TTL should produce a single set of DB hits."""
    from memos import server

    monkeypatch.setattr("memos.utils.watch_state.is_alive", lambda: True)
    monkeypatch.setattr("memos.utils.watch_state.is_on_battery", lambda: False)
    monkeypatch.setattr("memos.utils.watch_state.is_within_idle_window", lambda *a, **kw: True)

    # Force a long TTL so the second call definitely hits cache.
    monkeypatch.setattr(server, "_PROCESSING_STATUS_TTL", 60.0)
    # Clear any prior cache state.
    server._processing_status_cache.clear()

    lib_id = _seed_record_lib(engine, n_plugins=1, entity_specs=[(5, 0)])

    calls = {"n": 0}
    real_count = server.crud.count_entities_in_window

    def counting_count(*args, **kwargs):
        calls["n"] += 1
        return real_count(*args, **kwargs)

    monkeypatch.setattr(server.crud, "count_entities_in_window", counting_count)

    client.get(f"/api/libraries/{lib_id}/processing-status").raise_for_status()
    client.get(f"/api/libraries/{lib_id}/processing-status").raise_for_status()
    assert calls["n"] == 1


def test_watch_state_is_live_even_on_cache_hit(client, engine, monkeypatch):
    """Watch liveness is evaluated fresh per request; only the DB counts are cached.

    A dead/restarted watcher must be reflected immediately, not after the TTL.
    """
    from memos import server

    monkeypatch.setattr("memos.utils.watch_state.is_on_battery", lambda: False)
    monkeypatch.setattr("memos.utils.watch_state.is_within_idle_window", lambda *a, **kw: True)

    monkeypatch.setattr(server, "_PROCESSING_STATUS_TTL", 60.0)
    server._processing_status_cache.clear()

    lib_id = _seed_record_lib(engine, n_plugins=1, entity_specs=[(5, 0)])

    # Count the expensive DB call to prove the second response is a counts-cache hit.
    calls = {"n": 0}
    real_count = server.crud.count_entities_in_window

    def counting_count(*args, **kwargs):
        calls["n"] += 1
        return real_count(*args, **kwargs)

    monkeypatch.setattr(server.crud, "count_entities_in_window", counting_count)

    alive = {"v": True}
    monkeypatch.setattr("memos.utils.watch_state.is_alive", lambda: alive["v"])

    first = client.get(f"/api/libraries/{lib_id}/processing-status").json()
    assert first["watch"]["is_alive"] is True

    # Watcher dies between polls.
    alive["v"] = False
    second = client.get(f"/api/libraries/{lib_id}/processing-status").json()

    # Liveness reflects the present immediately...
    assert second["watch"]["is_alive"] is False
    # ...while the expensive counts came from cache (computed once) and are unchanged,
    # and computed_at stays pinned to when those counts were taken (honest staleness).
    assert calls["n"] == 1
    assert second["coverage_window"] == first["coverage_window"]
    assert second["backlog"] == first["backlog"]
    assert second["computed_at"] == first["computed_at"]
