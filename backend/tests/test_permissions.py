import pytest

from .helpers import build_world, lifecycle, make_rfq, register, login


@pytest.mark.parametrize("method,path", [("get", "/vendors"), ("get", "/rfqs"), ("get", "/approvals"), ("get", "/activity"),
                                          ("get", "/reports/summary"), ("get", "/reports/export?kind=monthly")])
def test_vendor_role_is_kept_out_of_staff_areas(client, method, path):
    w = build_world(client)
    assert getattr(client, method)(path, headers=w["arden"]).status_code == 403


@pytest.mark.parametrize("path", ["/vendors", "/rfqs", "/approvals", "/activity", "/reports/summary", "/purchase-orders",
                                  "/invoices", "/notifications", "/my/rfqs"])
def test_every_module_requires_login(client, path):
    assert client.get(path).status_code == 401


def test_manager_can_read_rfqs_but_not_create_or_manage_them(client):
    w = build_world(client)
    rfq = make_rfq(client, w)
    assert client.get("/rfqs", headers=w["mgr1"]).status_code == 200
    assert client.get(f"/rfqs/{rfq['id']}", headers=w["mgr1"]).status_code == 200
    from .helpers import rfq_body
    assert client.post("/rfqs", headers=w["mgr1"], json=rfq_body(w)).status_code == 403
    assert client.patch(f"/rfqs/{rfq['id']}/status", headers=w["mgr1"], json=dict(status="closed")).status_code == 403
    assert client.delete(f"/rfqs/{rfq['id']}", headers=w["mgr1"]).status_code == 403


def test_only_admin_and_manager_can_delete_vendors(client):
    w = build_world(client)
    vid = w["vendors"]["blue"]
    assert client.delete(f"/vendors/{vid}", headers=w["officer"]).status_code == 403
    assert client.delete(f"/vendors/{vid}", headers=w["mgr1"]).status_code == 204


def test_a_vendor_cannot_reach_another_vendors_documents(client):
    w = build_world(client)
    ids = lifecycle(client, w, vendor="arden")
    po_id, inv_id = ids["po"]["id"], ids["invoice"]["id"]
    for key, code in (("arden", 200), ("kestrel", 404), ("maple", 404)):
        assert client.get(f"/purchase-orders/{po_id}", headers=w[key]).status_code == code
        assert client.get(f"/invoices/{inv_id}", headers=w[key]).status_code == code
        assert client.get(f"/invoices/{inv_id}/pdf", headers=w[key]).status_code == code
    assert len(client.get("/purchase-orders", headers=w["kestrel"]).json()) == 0
    assert len(client.get("/purchase-orders", headers=w["arden"]).json()) == 1
    assert len(client.get("/invoices", headers=w["arden"]).json()) == 1


def test_a_vendor_user_without_a_vendor_profile_gets_a_clear_refusal(client):
    w = build_world(client)
    register(client, "stranger@x.com", "vendor")
    h = login(client, "stranger@x.com")
    r = client.get("/my/rfqs", headers=h)
    assert r.status_code == 403 and "vendor profile" in r.json()["detail"]


def test_staff_cannot_use_the_vendor_portal(client):
    w = build_world(client)
    assert client.get("/my/rfqs", headers=w["officer"]).status_code == 403


def test_a_vendor_cannot_see_rfqs_it_was_not_assigned(client):
    w = build_world(client)
    rfq = make_rfq(client, w, vendors=("arden",))
    assert client.get(f"/my/rfqs/{rfq['id']}", headers=w["arden"]).status_code == 200
    assert client.get(f"/my/rfqs/{rfq['id']}", headers=w["kestrel"]).status_code == 404
    assert client.get("/my/rfqs", headers=w["kestrel"]).json() == []