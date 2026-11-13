from datetime import date, timedelta

from app.database import SessionLocal
from app.models import RFQ
from .helpers import build_world, make_rfq, quotation_ids, register, login, submit_standard_quotes, to_approved


def ready(client, w, vendor="arden"):
    rfq = make_rfq(client, w)
    submit_standard_quotes(client, w, rfq["id"])
    qid = quotation_ids(client, w, rfq["id"])[vendor]
    client.put(f"/rfqs/{rfq['id']}/selected-quotation", headers=w["officer"], json=dict(quotation_id=qid))
    return rfq


def test_cannot_submit_without_a_selected_quotation(client):
    w = build_world(client)
    rfq = make_rfq(client, w)
    submit_standard_quotes(client, w, rfq["id"])
    assert client.post("/approvals", headers=w["officer"], json=dict(rfq_id=rfq["id"])).status_code == 409


def test_only_officers_can_submit_for_approval(client):
    w = build_world(client)
    rfq = ready(client, w)
    for key in ("mgr1", "arden"):
        assert client.post("/approvals", headers=w[key], json=dict(rfq_id=rfq["id"])).status_code == 403


def test_workflow_states_and_timeline(client):
    w = build_world(client)
    rfq = ready(client, w)
    a = client.post("/approvals", headers=w["officer"], json=dict(rfq_id=rfq["id"])).json()
    assert a["status"] == "awaiting_l1" and a["total"] == 200010.0
    assert [t["status"] for t in a["timeline"]] == ["done", "current", "pending", "pending"]
    r = client.post(f"/approvals/{a['id']}/decision", headers=w["mgr1"], json=dict(decision="approve", remarks="Looks fine")).json()
    assert r["status"] == "awaiting_l2" and [t["status"] for t in r["timeline"]] == ["done", "done", "current", "pending"]
    assert r["timeline"][1]["actor"] == "Mgr1 User" and r["timeline"][1]["remarks"] == "Looks fine" and r["timeline"][1]["at"]
    r = client.post(f"/approvals/{a['id']}/decision", headers=w["mgr2"], json=dict(decision="approve")).json()
    assert r["status"] == "approved" and r["completed_at"]
    assert [t["status"] for t in r["timeline"]] == ["done", "done", "done", "current"]


def test_duplicate_requests_and_locks(client):
    w = build_world(client)
    rfq = ready(client, w)
    assert client.post("/approvals", headers=w["officer"], json=dict(rfq_id=rfq["id"])).status_code == 201
    assert client.post("/approvals", headers=w["officer"], json=dict(rfq_id=rfq["id"])).status_code == 409
    other = quotation_ids(client, w, rfq["id"])["kestrel"]
    assert client.put(f"/rfqs/{rfq['id']}/selected-quotation", headers=w["officer"], json=dict(quotation_id=other)).status_code == 409
    assert client.patch(f"/rfqs/{rfq['id']}/status", headers=w["officer"], json=dict(status="cancelled")).status_code == 409


def test_who_may_decide(client):
    w = build_world(client)
    rfq = ready(client, w)
    aid = client.post("/approvals", headers=w["officer"], json=dict(rfq_id=rfq["id"])).json()["id"]
    decide = lambda h, **kw: client.post(f"/approvals/{aid}/decision", headers=w[h], json=kw)
    assert decide("officer", decision="approve").status_code == 403           # officers cannot approve
    assert decide("arden", decision="approve").status_code == 403             # vendors cannot even see approvals
    assert decide("mgr1", decision="bogus").status_code == 422
    assert decide("mgr1", decision="reject").status_code == 422               # a rejection needs remarks
    assert decide("mgr1", decision="reject", remarks="no").status_code == 422  # and real remarks
    assert decide("mgr1", decision="approve").status_code == 200
    assert decide("mgr1", decision="approve").status_code == 403              # the same person cannot give both levels
    assert decide("mgr2", decision="approve").status_code == 200
    assert decide("admin", decision="reject", remarks="too late now").status_code == 409  # already finished


def test_a_requester_cannot_approve_their_own_request(client):
    w = build_world(client)
    rfq = ready(client, w)
    aid = client.post("/approvals", headers=w["admin"], json=dict(rfq_id=rfq["id"])).json()["id"]  # admin may also act as officer
    r = client.post(f"/approvals/{aid}/decision", headers=w["admin"], json=dict(decision="approve"))
    assert r.status_code == 403 and "submitted" in r.json()["detail"]
    assert client.post(f"/approvals/{aid}/decision", headers=w["mgr1"], json=dict(decision="approve")).status_code == 200


def test_rejection_ends_the_request_and_allows_a_resubmission(client):
    w = build_world(client)
    rfq = ready(client, w)
    aid = client.post("/approvals", headers=w["officer"], json=dict(rfq_id=rfq["id"])).json()["id"]
    r = client.post(f"/approvals/{aid}/decision", headers=w["mgr1"], json=dict(decision="reject", remarks="Price too high")).json()
    assert r["status"] == "rejected" and [t["status"] for t in r["timeline"]] == ["done", "rejected", "skipped", "skipped"]
    assert client.post("/purchase-orders", headers=w["officer"], json=dict(approval_id=aid)).status_code == 409
    # the selection unlocks, and a new request can be made
    other = quotation_ids(client, w, rfq["id"])["maple"]
    assert client.put(f"/rfqs/{rfq['id']}/selected-quotation", headers=w["officer"], json=dict(quotation_id=other)).status_code == 200
    again = client.post("/approvals", headers=w["officer"], json=dict(rfq_id=rfq["id"]))
    assert again.status_code == 201 and again.json()["id"] != aid
    ids = [a["status"] for a in client.get("/approvals", headers=w["admin"]).json()]
    assert sorted(ids) == ["awaiting_l1", "rejected"]  # history is kept


def test_list_filter_and_missing_records(client):
    w = build_world(client)
    rfq = ready(client, w)
    client.post("/approvals", headers=w["officer"], json=dict(rfq_id=rfq["id"]))
    assert len(client.get("/approvals?status_filter=awaiting_l1", headers=w["mgr1"]).json()) == 1
    assert client.get("/approvals?status_filter=approved", headers=w["mgr1"]).json() == []
    assert client.get("/approvals/9999", headers=w["mgr1"]).status_code == 404
    assert client.post("/approvals/9999/decision", headers=w["mgr1"], json=dict(decision="approve")).status_code == 404
    assert client.post("/approvals", headers=w["officer"], json=dict(rfq_id=9999)).status_code == 404