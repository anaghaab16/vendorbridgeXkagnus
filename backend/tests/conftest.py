"""Test setup. The tests build and wipe their own database, so they must never point at the real one."""
import os

TEST_DB = os.environ.get("TEST_DATABASE_URL", "sqlite:///./test_vendorbridge.db")
if not ("sqlite" in TEST_DB or "localhost" in TEST_DB or "127.0.0.1" in TEST_DB):
    raise SystemExit("Refusing to run: TEST_DATABASE_URL must be SQLite or a local database, never a hosted one.")
os.environ["DATABASE_URL"] = TEST_DB  # environment variables win over backend/.env
os.environ["SECRET_KEY"] = "test-secret-key-used-only-by-the-test-suite"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event  # noqa: E402

from app import main  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import Base, engine  # noqa: E402

if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def _foreign_keys_on(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")


import bcrypt  # noqa: E402

_real_gensalt = bcrypt.gensalt


@pytest.fixture(autouse=True)
def fresh_database(monkeypatch):
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=4, prefix=b"2b": _real_gensalt(rounds=4, prefix=prefix))  # fast hashing in tests
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    main.protect_audit_log()
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "smtp_from", "")
    monkeypatch.setattr(settings, "company_name", "Acme Procurement Pvt Ltd")
    monkeypatch.setattr(settings, "company_address", "12 MG Road, Mysuru")
    monkeypatch.setattr(settings, "company_gstin", "29AABCA1234A1Z5")
    yield


@pytest.fixture
def client():
    return TestClient(main.app)