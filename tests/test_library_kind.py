"""Test library.kind discriminator: API exposure, PATCH, and context gating."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from memos.models import (
    Base,
    EntityModel,
    FolderModel,
    LibraryModel,
)
from memos.schemas import FolderType, LibraryKind
from memos.server import api_router, app, get_db


@pytest.fixture
def engine():
    # StaticPool + shared connection so the API request and the test
    # setup observe the same in-memory database.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(engine):
    SessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    # /api routes live on a child FastAPI app, so the override has to be
    # registered on that one to take effect.
    api_router.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        api_router.dependency_overrides.pop(get_db, None)


def _seed_library(engine, kind: LibraryKind, name: str | None = None) -> int:
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as db:
        lib = LibraryModel(name=name or f"lib-{kind.value}", kind=kind)
        db.add(lib)
        db.flush()
        folder = FolderModel(
            path="/x",
            library_id=lib.id,
            type=FolderType.DEFAULT,
            last_modified_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )
        db.add(folder)
        db.flush()
        for i in range(3):
            db.add(
                EntityModel(
                    filepath=f"/x/{lib.id}-{i}.webp",
                    filename=f"{i}.webp",
                    size=1,
                    file_created_at=datetime(2026, 5, 1, 0, 0, i, tzinfo=timezone.utc),
                    file_last_modified_at=datetime(2026, 5, 1, 0, 0, i, tzinfo=timezone.utc),
                    file_type="webp",
                    file_type_group="image",
                    library_id=lib.id,
                    folder_id=folder.id,
                )
            )
        db.commit()
        return lib.id


def _middle_entity_id(engine, lib_id: int) -> int:
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as db:
        entity = (
            db.query(EntityModel)
            .filter(EntityModel.library_id == lib_id)
            .order_by(EntityModel.file_created_at)
            .offset(1)
            .first()
        )
        return entity.id


def test_get_libraries_exposes_kind(engine, client):
    _seed_library(engine, LibraryKind.RECORD, name="lib-record")
    _seed_library(engine, LibraryKind.STATIC, name="lib-static")

    resp = client.get("/api/libraries")
    assert resp.status_code == 200
    kinds = sorted(lib["kind"] for lib in resp.json())
    assert kinds == ["record", "static"]


def test_patch_library_kind_round_trip(engine, client):
    lib_id = _seed_library(engine, LibraryKind.STATIC)

    resp = client.patch(f"/api/libraries/{lib_id}", json={"kind": "record"})
    assert resp.status_code == 200
    assert resp.json()["kind"] == "record"

    # Confirm the change persists across a fresh GET.
    resp = client.get(f"/api/libraries/{lib_id}")
    assert resp.json()["kind"] == "record"


def test_patch_unknown_library_returns_404(client):
    resp = client.patch("/api/libraries/9999", json={"kind": "record"})
    assert resp.status_code == 404


def test_context_is_empty_for_static_library(engine, client):
    lib_id = _seed_library(engine, LibraryKind.STATIC)
    entity_id = _middle_entity_id(engine, lib_id)

    resp = client.get(
        f"/api/libraries/{lib_id}/entities/{entity_id}/context",
        params={"prev": 12, "next": 12},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Static libraries get no temporal context even when neighbors exist.
    assert body["prev"] == []
    assert body["next"] == []


def test_context_works_for_record_library(engine, client):
    lib_id = _seed_library(engine, LibraryKind.RECORD)
    entity_id = _middle_entity_id(engine, lib_id)

    resp = client.get(
        f"/api/libraries/{lib_id}/entities/{entity_id}/context",
        params={"prev": 12, "next": 12},
    )
    assert resp.status_code == 200
    body = resp.json()
    # The middle entity should see one neighbor on each side.
    assert len(body["prev"]) == 1
    assert len(body["next"]) == 1
