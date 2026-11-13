from datetime import date, timedelta

import pytest

from app.database import SessionLocal
from app.models import RFQ
from .helpers import STANDARD, build_world, item_ids, make_rfq, quote, quotation_ids, rfq_body, submit_standard_quotes


@pytest.mark.parametrize("change,expected", [
    ({"deadline": (date.today() - timedelta(days=1)).isoformat()}, 422),
    ({"items": []}, 422),
    ({"items": [dict(item_name="Chair", quantity=0, unit="pcs")]}, 422),
    ({"items": [dict(item_name="Chair", quantity=-3, unit="pcs")]}, 422),
    ({"title": "ab"}, 422),
    ({"vendor_ids": []}, 422),             # sending with nobody to send to
    ({"vendor_ids": [9999]}, 422),         # unknown vendor
])
def test_invalid_rfqs_are_refused(client, change, expected):
    w = build_world(client)
    assert client.post("/rfqs", headers=w["officer"], json=rfq_body(w, **change)).status_code == expected


def test_blocked_vendor_cannot_be_assigned(client):
    w = build_world(client)
    r = client.post("/rfqs", headers=w["officer"], json=rfq_body(w, vendors=("arden", "blue")))
    assert r.status_code == 422 and "Blocked" in r.json()["detail"]


def test_rfq_numbers_are_unique_and_formatted(client):
    w = build_world(client)
    a, b = make_rfq(client, w), make_rfq(client, w)
    assert a["rfq_number"] != b["rfq_number"]
    assert a["rfq_number"].startswith(f"RFQ-{date.today().year}-")


def test_draft_is_invisible_to_vendors_until_sent(client):
    w = build_world(client)
    rfq = make_rfq(client, w, send=False)
    assert client.get("/my/rfqs", headers=w["arden"]).json() == []
    assert client.patch(f"/rfqs/{rfq['id']}/status", headers=w["officer"], json=dict(status="sent")).status_code == 200
    assert len(client.get("/my/rfqs", headers=w["arden"]).json()) == 1


def test_quotation_validation(client):
    w = build_world(client)
    rfq = make_rfq(client, w)
    ids = item_ids(client, w, rfq["id"])
    other = make_rfq(client, w)
    other_ids = item_ids(client, w, other["id"])
    h = w["arden"]
    assert quote(client, h, rfq["id"], ids[:1], [3500]).status_code == 422                 # an item is missing
    assert quote(client, h, rfq["id"], ids, [0, 8200]).status_code == 422                  # zero price
    assert quote(client, h, rfq["id"], ids, [3500, 8200], days=None).status_code == 422    # no delivery time
    assert quote(client, h, rfq["id"], ids, [3500.555, 8200]).status_code == 422           # three decimals
    assert quote(client, h, rfq["id"], ids, [-5, 8200]).status_code == 422                 # negative
    assert quote(client, h, rfq["id"], other_ids[:1] + ids[1:], [3500, 8200]).status_code == 422  # item of another RFQ
    assert quote(client, h, rfq["id"], ids, [3500, 8200], gst=150).status_code == 422
    assert quote(client, h, rfq["id"], ids, [3500, 8200], days=0).status_code == 422


def test_draft_quotation_is_saved_but_hidden_from_comparison(client):
    w = build_world(client)
    rfq = make_rfq(client, w)
    ids = item_ids(client, w, rfq["id"])
    r = quote(client, w["arden"], rfq["id"], ids[:1], [3500], submit=False)
    assert r.status_code == 200 and r.json()["status"] == "draft"
    assert client.get(f"/rfqs/{rfq['id']}/comparison", headers=w["officer"]).json()["quotes"] == []


def test_a_submitted_quotation_can_be_edited_before_the_deadline_and_stays_submitted(client):
    w = build_world(client)
    rfq = make_rfq(client, w)
    ids = item_ids(client, w, rfq["id"])
    assert quote(client, w["arden"], rfq["id"], ids, [3500, 8200]).json()["total"] == 200010.0
    r = quote(client, w["arden"], rfq["id"], ids, [3400, 8200], submit=False)  # "save" on a submitted quotation
    assert r.status_code == 200 and r.json()["status"] == "submitted"
    assert r.json()["subtotal"] == round(3400 * 25 + 8200 * 10, 2)
    # persists across sessions
    again = client.get(f"/my/rfqs/{rfq['id']}", headers=w["arden"]).json()["quotation"]
    assert again["total"] == r.json()["total"]


def test_quotations_are_refused_after_the_deadline(client):
    w = build_world(client)
    rfq = make_rfq(client, w)
    ids = item_ids(client, w, rfq["id"])
    assert quote(client, w["arden"], rfq["id"], ids, [3500, 8200]).status_code == 200
    with SessionLocal() as db:
        db.get(RFQ, rfq["id"]).deadline = date.today() - timedelta(days=1)
        db.commit()
    r = quote(client, w["arden"], rfq["id"], ids, [1, 1])
    assert r.status_code == 403 and "deadline" in r.json()["detail"]
    assert client.get(f"/my/rfqs/{rfq['id']}", headers=w["arden"]).json()["can_edit"] is False  # still readable


def test_deadline_day_itself_is_still_open(client):
    w = build_world(client)
    rfq = make_rfq(client, w, days=0)
    ids = item_ids(client, w, rfq["id"])
    assert quote(client, w["arden"], rfq["id"], ids, [3500, 8200]).status_code == 200


def test_closed_rfq_refuses_quotations(client):
    w = build_world(client)
    rfq = make_rfq(client, w)
    ids = item_ids(client, w, rfq["id"])
    client.patch(f"/rfqs/{rfq['id']}/status", headers=w["officer"], json=dict(status="closed"))
    assert quote(client, w["arden"], rfq["id"], ids, [3500, 8200]).status_code == 409


def test_unassigned_vendor_cannot_quote(client):
    w = build_world(client)
    rfq = make_rfq(client, w, vendors=("arden",))
    ids = item_ids(client, w, rfq["id"])
    assert quote(client, w["kestrel"], rfq["id"], ids, [3500, 8200]).status_code == 404


def test_comparison_flags_lowest_price_and_fastest_delivery(client):
    w = build_world(client)
    rfq = make_rfq(client, w)
    submit_standard_quotes(client, w, rfq["id"])
    cmp_ = client.get(f"/rfqs/{rfq['id']}/comparison", headers=w["officer"]).json()
    by = {q["vendor_name"].split()[0]: q for q in cmp_["quotes"]}
    assert by["Arden"]["total"] == 200010.0 and by["Kestrel"]["total"] == 206500.0 and by["Maple"]["total"] == 203845.0
    assert [n for n, q in by.items() if q["is_lowest"]] == ["Arden"]
    assert [n for n, q in by.items() if q["is_fastest"]] == ["Maple"]
    assert by["Arden"]["rating"] == 4.5


def test_comparison_empty_state_and_waiting_list(client):
    w = build_world(client)
    rfq = make_rfq(client, w)
    empty = client.get(f"/rfqs/{rfq['id']}/comparison", headers=w["officer"]).json()
    assert empty["quotes"] == [] and len(empty["waiting"]) == 3
    submit_standard_quotes(client, w, rfq["id"], who=("arden",))
    assert len(client.get(f"/rfqs/{rfq['id']}/comparison", headers=w["officer"]).json()["waiting"]) == 2


def test_selection_rules(client):
    w = build_world(client)
    rfq, other = make_rfq(client, w), make_rfq(client, w)
    submit_standard_quotes(client, w, rfq["id"])
    submit_standard_quotes(client, w, other["id"], who=("arden",))
    mine = quotation_ids(client, w, rfq["id"])
    foreign = quotation_ids(client, w, other["id"])["arden"]
    sel = lambda rid, qid, h="officer": client.put(f"/rfqs/{rid}/selected-quotation", headers=w[h], json=dict(quotation_id=qid))
    assert sel(rfq["id"], mine["arden"], "mgr1").status_code == 403          # only officers select
    assert sel(rfq["id"], foreign).status_code == 422                           # a quotation of another RFQ
    assert sel(rfq["id"], 99999).status_code == 422
    assert sel(rfq["id"], mine["arden"]).status_code == 200
    r = sel(rfq["id"], mine["kestrel"]).json()                                  # changing the choice leaves exactly one selected
    assert sum(q["is_selected"] for q in r["quotes"]) == 1 and r["selected_quotation_id"] == mine["kestrel"]
    assert sel(rfq["id"], None).json()["selected_quotation_id"] is None


def test_a_selected_quotation_is_locked_for_the_vendor(client):
    w = build_world(client)
    rfq = make_rfq(client, w)
    ids = submit_standard_quotes(client, w, rfq["id"])
    qid = quotation_ids(client, w, rfq["id"])["arden"]
    client.put(f"/rfqs/{rfq['id']}/selected-quotation", headers=w["officer"], json=dict(quotation_id=qid))
    assert quote(client, w["arden"], rfq["id"], ids, [1000, 1000]).status_code == 409


def test_attachments(client):
    w = build_world(client)
    rfq = make_rfq(client, w, vendors=("arden",))
    up = lambda name, data, h="officer": client.post(f"/rfqs/{rfq['id']}/attachments", headers=w[h], files={"file": (name, data)})
    ok = up("spec.pdf", b"%PDF-1.4 test")
    assert ok.status_code == 201
    assert up("virus.exe", b"MZ").status_code == 422
    assert up("empty.pdf", b"").status_code == 422
    assert up("big.pdf", b"x" * (5 * 1024 * 1024 + 1)).status_code == 413
    assert up("spec.pdf", b"x", "mgr1").status_code == 403
    url = f"/rfqs/{rfq['id']}/attachments/{ok.json()['id']}"
    assert client.get(url, headers=w["arden"]).content == b"%PDF-1.4 test"      # the assigned vendor can download
    assert client.get(url, headers=w["kestrel"]).status_code == 404               # another vendor cannot
    assert client.get(url).status_code == 401