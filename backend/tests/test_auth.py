import pytest

from app.database import SessionLocal
from app.models import User
from .helpers import PASSWORD, login, register


def test_register_then_login_returns_the_user(client):
    register(client, "ana@x.com", "procurement_officer", first="Ana")
    h = login(client, "ana@x.com")
    me = client.get("/auth/me", headers=h).json()
    assert me["email"] == "ana@x.com" and me["role"] == "procurement_officer" and me["name"] == "Ana User"
    assert "password" not in me and "password_hash" not in me


def test_email_is_case_insensitive(client):
    register(client, "Ana@X.com", "procurement_officer")
    assert client.post("/auth/login", json=dict(email="ANA@x.COM", password=PASSWORD)).status_code == 200


def test_duplicate_email_is_refused(client):
    register(client, "ana@x.com", "procurement_officer")
    r = client.post("/auth/register", json=dict(first_name="A", last_name="B", email="ana@x.com", phone="+91 98765 43210",
                                                role="vendor", country="India", password=PASSWORD))
    assert r.status_code == 409


@pytest.mark.parametrize("field,value", [("password", "short"), ("password", "x" * 80), ("phone", "123"), ("email", "not-an-email"),
                                         ("country", "")])
def test_invalid_registration_is_refused(client, field, value):
    body = dict(first_name="A", last_name="B", email="a@x.com", phone="+91 98765 43210", role="vendor", country="India", password=PASSWORD)
    body[field] = value
    assert client.post("/auth/register", json=body).status_code == 422


def test_only_one_admin_can_be_created_from_the_form(client):
    register(client, "admin@x.com", "admin")
    r = client.post("/auth/register", json=dict(first_name="B", last_name="B", email="admin2@x.com", phone="+91 98765 43210",
                                                role="admin", country="India", password=PASSWORD))
    assert r.status_code == 403


def test_wrong_password_and_unknown_user_get_the_same_answer(client):
    register(client, "ana@x.com", "procurement_officer")
    wrong = client.post("/auth/login", json=dict(email="ana@x.com", password="wrong-password"))
    unknown = client.post("/auth/login", json=dict(email="nobody@x.com", password=PASSWORD))
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()  # does not reveal which emails exist


def test_inactive_account_cannot_log_in(client):
    register(client, "ana@x.com", "procurement_officer")
    with SessionLocal() as db:
        u = db.query(User).filter_by(email="ana@x.com").one()
        u.is_active = False
        db.commit()
    assert client.post("/auth/login", json=dict(email="ana@x.com", password=PASSWORD)).status_code == 401


def test_protected_routes_need_a_valid_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer not.a.token"}).status_code == 401
    assert client.get("/vendors").status_code == 401


def test_a_token_for_a_deleted_user_stops_working(client):
    register(client, "ana@x.com", "procurement_officer")
    h = login(client, "ana@x.com")
    with SessionLocal() as db:
        u = db.query(User).filter_by(email="ana@x.com").one()
        u.is_active = False
        db.commit()
    assert client.get("/auth/me", headers=h).status_code == 401