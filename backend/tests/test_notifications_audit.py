import pytest
from sqlalchemy import text

from app.database import SessionLocal, engine
from app.models import AuditLog
from .helpers import build_world, item_ids, lifecycle, make_rfq, quote, quotation_ids, submit_standard_quotes


def inbox(client, w, who, **params):
    return client.get("/notifications", headers=w[who], params=params).json()


def kinds(client, w, who):
    return [n["kind"] for n in inbox(client, w, who)]


def test_sending_an_rfq_notifies_only_the_assigned_vendors(client):
    w = build_world(client)
    rfq = make_rfq(client, w, vendors=("arden", "kestrel"))
    for who in ("arden", "kestrel"):
        n = inbox(client, w, who)
        assert [x["kind"] for x in n] == ["rfq.sent"] and rfq["rfq_number"] in n[0]["message"]
        assert n[0]["link"] == f"/my-rfqs/{rfq['id']}" and n[0]["entity_type"] == "rfq" and n[0]["entity_id"] == rfq["id"]
        assert n[0]["is_read"] is False and n[0]["created_at"]
    assert inbox(client, w, "maple") == []          # not assigned
    assert inbox(client, w, "officer") == []        # nobody is told about their own action


def test_a_draft_notifies_nobody_until_it_is_sent(client):
    w = build_world(client)
    rfq = make_rfq(client, w, send=False)
    assert inbox(client, w, "arden") == []
    client.patch(f"/rfqs/{rfq['id']}/status", headers=w["officer"], json=dict(status="sent"))
    assert kinds(client, w, "arden") == ["rfq.sent"]


def test_closing_and_cancelling_notify_vendors_of_a_sent_rfq(client):
    w = build_world(client)
    rfq = make_rfq(client, w, vendors=("arden",))
    client.patch(f"/rfqs/{rfq['id']}/status", headers=w["officer"], json=dict(status="closed"))
    assert kinds(client, w, "arden") == ["rfq.closed", "rfq.sent"]
    draft = make_rfq(client, w, vendors=("arden",), send=False)
    client.patch(f"/rfqs/{draft['id']}/status", headers=w["officer"], json=dict(status="cancelled"))
    assert len(inbox(client, w, "arden")) == 2      # a cancelled draft was never sent, so no message


def test_notifications_follow_the_whole_lifecycle(client):
    w = build_world(client)
    ids = lifecycle(client, w)
    # the officer hears about quotations and approval progress, never about their own actions
    assert kinds(client, w, "officer").count("quotation.submitted") == 3
    assert {"approval.l1_approved", "approval.approved"} <= set(kinds(client, w, "officer"))
    assert "po.created" not in kinds(client, w, "officer")   # the same person created the PO, so nothing to tell them
    assert "approval.requested" not in kinds(client, w, "officer")
    # approvers are asked once and told when the second approval is due
    assert kinds(client, w, "mgr1").count("approval.requested") == 1
    assert "approval.l1_approved" in kinds(client, w, "mgr2")
    assert "approval.l1_approved" not in kinds(client, w, "mgr1")   # mgr1 did it themselves
    # the chosen vendor is told about the PO and invoice; the others are not
    assert {"po.issued", "invoice.created"} <= set(kinds(client, w, "arden"))
    assert "po.issued" not in kinds(client, w, "kestrel") and "invoice.created" not in kinds(client, w, "maple")
    po = next(n for n in inbox(client, w, "arden") if n["kind"] == "po.issued")
    assert po["link"] == f"/purchase-orders/{ids['po']['id']}" and ids["po"]["po_number"] in po["message"]
    client.patch(f"/invoices/{ids['invoice']['id']}/mark-paid", headers=w["mgr1"])
    assert "invoice.paid" in kinds(client, w, "arden") and "invoice.paid" in kinds(client, w, "officer")


def test_rejection_tells_the_requester_why(client):
    w = build_world(client)
    rfq = make_rfq(client, w)
    submit_standard_quotes(client, w, rfq["id"])
    qid = quotation_ids(client, w, rfq["id"])["arden"]
    client.put(f"/rfqs/{rfq['id']}/selected-quotation", headers=w["officer"], json=dict(quotation_id=qid))
    aid = client.post("/approvals", headers=w["officer"], json=dict(rfq_id=rfq["id"])).json()["id"]
    client.post(f"/approvals/{aid}/decision", headers=w["mgr1"], json=dict(decision="reject", remarks="Price too high"))
    n = next(x for x in inbox(client, w, "officer") if x["kind"] == "approval.rejected")
    assert "Price too high" in n["message"] and n["link"] == f"/approvals/{aid}"


def test_read_unread_and_privacy(client):
    w = build_world(client)
    make_rfq(client, w)
    assert client.get("/notifications/unread-count", headers=w["arden"]).json() == {"count": 1}
    nid = inbox(client, w, "arden")[0]["id"]
    assert client.post(f"/notifications/{nid}/read", headers=w["kestrel"]).status_code == 404   # not theirs
    assert client.get("/notifications/unread-count", headers=w["arden"]).json() == {"count": 1}
    r = client.post(f"/notifications/{nid}/read", headers=w["arden"]).json()
    assert r["is_read"] is True
    assert client.get("/notifications/unread-count", headers=w["arden"]).json() == {"count": 0}
    assert inbox(client, w, "arden", unread_only=True) == []
    assert len(inbox(client, w, "arden")) == 1
    make_rfq(client, w)
    make_rfq(client, w)
    assert client.post("/notifications/read-all", headers=w["arden"]).json() == {"count": 0}
    assert client.get("/notifications/unread-count", headers=w["arden"]).json() == {"count": 0}
    assert client.get("/notifications/unread-count", headers=w["kestrel"]).json() == {"count": 3}   # unaffected
    assert client.post("/notifications/9999/read", headers=w["arden"]).status_code == 404


# ------------------------------------------------------------------ audit

def test_audit_log_records_real_actions_with_actor_record_and_time(client):
    w = build_world(client)
    ids = lifecycle(client, w)
    page = client.get("/activity?limit=200", headers=w["admin"]).json()
    actions = [i["action"] for i in page["items"]]
    for expected in ("user.registered", "vendor.created", "rfq.created", "quotation.submitted", "quotation.selected",
                     "approval.submitted", "approval.l1_approved", "approval.approved", "po.created", "invoice.created"):
        assert expected in actions, expected
    assert page["total"] == len(page["items"])
    times = [i["created_at"] for i in page["items"]]
    assert times == sorted(times, reverse=True)                                 # newest first
    po = next(i for i in page["items"] if i["action"] == "po.created")
    assert po["actor_name"] == "Officer User" and po["actor_role"] == "procurement_officer"
    assert po["entity_type"] == "purchase_order" and po["entity_id"] == ids["po"]["id"] and po["entity_label"] == ids["po"]["po_number"]
    sub = next(i for i in page["items"] if i["action"] == "quotation.submitted" and i["actor_name"] == "Kestrel User")
    assert ids["rfq"]["rfq_number"] in sub["message"]


def test_actions_that_fail_leave_no_audit_record(client):
    w = build_world(client)
    before = client.get("/activity", headers=w["admin"]).json()["total"]
    client.post("/rfqs", headers=w["officer"], json={"title": "x"})                                    # invalid
    client.post("/vendors", headers=w["officer"], json=dict(name="Dup", email="arden@x.com"))         # duplicate email
    assert client.get("/activity", headers=w["admin"]).json()["total"] == before


def test_filtering_the_timeline(client):
    w = build_world(client)
    lifecycle(client, w)
    inv = client.get("/activity?entity_type=invoice", headers=w["admin"]).json()
    assert inv["total"] >= 1 and {i["entity_type"] for i in inv["items"]} == {"invoice"}
    page1 = client.get("/activity?limit=5&offset=0", headers=w["admin"]).json()
    page2 = client.get("/activity?limit=5&offset=5", headers=w["admin"]).json()
    assert len(page1["items"]) == 5 and {i["id"] for i in page1["items"]}.isdisjoint({i["id"] for i in page2["items"]})


def test_audit_visibility_by_role(client):
    w = build_world(client)
    lifecycle(client, w)
    admin = client.get("/activity?limit=200", headers=w["admin"]).json()["total"]
    assert client.get("/activity?limit=200", headers=w["mgr1"]).json()["total"] == admin
    officer = client.get("/activity?limit=200", headers=w["officer"]).json()
    assert 0 < officer["total"] < admin and {i["actor_name"] for i in officer["items"]} == {"Officer User"}
    for who in ("arden", "kestrel"):
        assert client.get("/activity", headers=w[who]).status_code == 403
    assert client.get("/activity").status_code == 401


def test_there_is_no_way_to_change_or_delete_audit_records_through_the_api(client):
    w = build_world(client)
    lifecycle(client, w)
    first = client.get("/activity", headers=w["admin"]).json()["items"][0]["id"]
    before = client.get("/activity?limit=200", headers=w["admin"]).json()
    for method in ("put", "patch", "delete", "post"):
        for path in ("/activity", f"/activity/{first}"):
            assert getattr(client, method)(path, headers=w["admin"]).status_code in (404, 405)
    assert client.get("/activity?limit=200", headers=w["admin"]).json() == before


def test_the_application_layer_refuses_to_edit_or_delete_audit_rows(client):
    w = build_world(client)
    with SessionLocal() as db:
        row = db.query(AuditLog).first()
        row.message = "tampered"
        with pytest.raises(ValueError):
            db.commit()
        db.rollback()
        db.delete(db.query(AuditLog).first())
        with pytest.raises(ValueError):
            db.commit()


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="database triggers exist on PostgreSQL only")
def test_the_database_itself_refuses_to_edit_or_delete_audit_rows(client):
    build_world(client)
    for sql in ("UPDATE audit_logs SET message = 'tampered'", "DELETE FROM audit_logs"):
        with pytest.raises(Exception, match="cannot be changed or deleted"):
            with engine.begin() as conn:
                conn.execute(text(sql))
    with engine.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM audit_logs WHERE message = 'tampered'")).scalar() == 0


def test_email_attempts_are_audited(client, monkeypatch):
    from unittest import mock
    from app.config import settings
    w = build_world(client)
    ids = lifecycle(client, w)
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "smtp_from", "billing@acme.test")
    url = f"/invoices/{ids['invoice']['id']}/email"
    with mock.patch("smtplib.SMTP"):
        client.post(url, headers=w["officer"], json={})
    with mock.patch("smtplib.SMTP", side_effect=OSError("down")):
        client.post(url, headers=w["officer"], json={})
    actions = [i["action"] for i in client.get("/activity?limit=200", headers=w["admin"]).json()["items"]]
    assert "invoice.emailed" in actions and "invoice.email_failed" in actions