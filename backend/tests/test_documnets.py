from datetime import date, timedelta
from io import BytesIO
from unittest import mock

import pypdf

from app.database import SessionLocal
from app.config import settings
from app.models import Invoice
from .helpers import build_world, lifecycle, make_rfq, quote, quotation_ids, submit_standard_quotes, to_approved


def approved(client, w, vendor="arden", prices=None, terms=None):
    rfq = make_rfq(client, w)
    ids = submit_standard_quotes(client, w, rfq["id"])
    if prices:
        r = quote(client, w[vendor], rfq["id"], ids, prices, terms=terms or "30 days")
        assert r.status_code == 200, r.text
    return rfq, to_approved(client, w, rfq["id"], vendor)


def test_po_only_from_an_approved_quotation(client):
    w = build_world(client)
    rfq = make_rfq(client, w)
    submit_standard_quotes(client, w, rfq["id"])
    qid = quotation_ids(client, w, rfq["id"])["arden"]
    client.put(f"/rfqs/{rfq['id']}/selected-quotation", headers=w["officer"], json=dict(quotation_id=qid))
    aid = client.post("/approvals", headers=w["officer"], json=dict(rfq_id=rfq["id"])).json()["id"]
    assert client.post("/purchase-orders", headers=w["officer"], json=dict(approval_id=aid)).status_code == 409   # awaiting L1
    client.post(f"/approvals/{aid}/decision", headers=w["mgr1"], json=dict(decision="approve"))
    assert client.post("/purchase-orders", headers=w["officer"], json=dict(approval_id=aid)).status_code == 409   # awaiting L2
    client.post(f"/approvals/{aid}/decision", headers=w["mgr2"], json=dict(decision="approve"))
    assert client.post("/purchase-orders", headers=w["mgr1"], json=dict(approval_id=aid)).status_code == 403      # managers do not create POs
    assert client.post("/purchase-orders", headers=w["officer"], json=dict(approval_id=9999)).status_code == 404
    assert client.post("/purchase-orders", headers=w["officer"], json=dict(approval_id=aid)).status_code == 201


def test_po_uses_database_figures_and_ignores_what_the_browser_sends(client):
    w = build_world(client)
    rfq, aid = approved(client, w)
    r = client.post("/purchase-orders", headers=w["officer"], json=dict(approval_id=aid, grand_total=1, subtotal=1, status="closed"))
    po = r.json()
    assert r.status_code == 201 and po["status"] == "issued"
    assert po["totals"]["subtotal"] == 169500.0 and po["totals"]["grand_total"] == 200010.0
    assert po["po_number"].startswith(f"PO-{date.today().year}-") and po["rfq_number"] == rfq["rfq_number"]
    assert [(i["item_name"], i["quantity"], i["unit_price"], i["line_total"]) for i in po["items"]] == [
        ("Ergonomic chair", 25, 3500.0, 87500.0), ("Standing desk", 10, 8200.0, 82000.0)]
    assert po["vendor"]["name"] == "Arden Supplies" and po["vendor"]["gstin"] == "29ABCDE1234F1Z5"
    assert po["buyer"]["name"] == "Acme Procurement Pvt Ltd" and po["payment_terms"] == "30 days" and po["delivery_days"] == 7


def test_same_state_vendor_gets_cgst_and_sgst(client):
    w = build_world(client)
    _, aid = approved(client, w, "arden")
    t = client.post("/purchase-orders", headers=w["officer"], json=dict(approval_id=aid)).json()["totals"]
    assert (t["cgst"], t["sgst"], t["igst"], t["tax_label"]) == (15255.0, 15255.0, 0.0, "CGST + SGST")
    assert t["subtotal"] + t["cgst"] + t["sgst"] == t["grand_total"]


def test_other_state_vendor_gets_igst(client):
    w = build_world(client)
    _, aid = approved(client, w, "kestrel")  # GSTIN starts 27, the buyer's starts 29
    t = client.post("/purchase-orders", headers=w["officer"], json=dict(approval_id=aid)).json()["totals"]
    assert (t["cgst"], t["sgst"], t["igst"], t["tax_label"]) == (0.0, 0.0, 31500.0, "IGST")
    assert t["grand_total"] == 206500.0


def test_money_is_calculated_exactly(client):
    w = build_world(client)
    _, aid = approved(client, w, "arden", prices=[3500.50, 8200.25])
    t = client.post("/purchase-orders", headers=w["officer"], json=dict(approval_id=aid)).json()["totals"]
    assert t["subtotal"] == 169515.0 and t["gst_total"] == 30512.7 and t["grand_total"] == 200027.7
    assert round(t["cgst"] + t["sgst"], 2) == t["gst_total"]


def test_an_odd_paisa_of_tax_is_never_lost(client):
    w = build_world(client)
    rfq = make_rfq(client, w, items=[dict(item_name="Pen", quantity=3, unit="pcs")])
    ids = [i["id"] for i in client.get(f"/rfqs/{rfq['id']}", headers=w["officer"]).json()["items"]]
    assert quote(client, w["arden"], rfq["id"], ids, [10.01], gst=5).status_code == 200
    aid = to_approved(client, w, rfq["id"], "arden")
    t = client.post("/purchase-orders", headers=w["officer"], json=dict(approval_id=aid)).json()["totals"]
    assert (t["subtotal"], t["gst_total"], t["grand_total"]) == (30.03, 1.5, 31.53) and t["cgst"] + t["sgst"] == t["gst_total"]


def test_duplicate_documents_are_refused(client):
    w = build_world(client)
    ids = lifecycle(client, w)
    assert client.post("/purchase-orders", headers=w["officer"], json=dict(approval_id=ids["approval_id"])).status_code == 409
    assert client.post("/invoices", headers=w["officer"], json=dict(po_id=ids["po"]["id"])).status_code == 409
    assert len(client.get("/purchase-orders", headers=w["officer"]).json()) == 1
    assert len(client.get("/invoices", headers=w["officer"]).json()) == 1


def test_invoice_rules_and_figures(client):
    w = build_world(client)
    _, aid = approved(client, w, "arden", prices=[3500.50, 8200.25], terms="45 days")
    po = client.post("/purchase-orders", headers=w["officer"], json=dict(approval_id=aid)).json()
    assert client.post("/invoices", headers=w["mgr1"], json=dict(po_id=po["id"])).status_code == 403
    assert client.post("/invoices", headers=w["arden"], json=dict(po_id=po["id"])).status_code == 403
    assert client.post("/invoices", headers=w["officer"], json=dict(po_id=9999)).status_code == 404
    inv = client.post("/invoices", headers=w["officer"], json=dict(po_id=po["id"], grand_total=1)).json()
    assert inv["invoice_number"].startswith(f"INV-{date.today().year}-") and inv["po_number"] == po["po_number"]
    assert inv["totals"] == {**po["totals"]} and inv["status"] == "pending_payment" and inv["is_overdue"] is False
    assert inv["due_date"] == (date.today() + timedelta(days=45)).isoformat()
    assert client.get(f"/purchase-orders/{po['id']}", headers=w["officer"]).json()["status"] == "invoiced"


def test_due_date_defaults_to_30_days(client):
    w = build_world(client)
    _, aid = approved(client, w, "arden", prices=[3500, 8200], terms="on delivery")
    po = client.post("/purchase-orders", headers=w["officer"], json=dict(approval_id=aid)).json()
    inv = client.post("/invoices", headers=w["officer"], json=dict(po_id=po["id"])).json()
    assert inv["due_date"] == (date.today() + timedelta(days=30)).isoformat()


def test_overdue_flag(client):
    w = build_world(client)
    ids = lifecycle(client, w)
    with SessionLocal() as db:
        db.get(Invoice, ids["invoice"]["id"]).due_date = date.today() - timedelta(days=3)
        db.commit()
    assert client.get(f"/invoices/{ids['invoice']['id']}", headers=w["officer"]).json()["is_overdue"] is True


def test_pdf_download(client):
    w = build_world(client)
    ids = lifecycle(client, w)
    r = client.get(f"/invoices/{ids['invoice']['id']}/pdf", headers=w["officer"])
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
    assert ids["invoice"]["invoice_number"] in r.headers["content-disposition"]
    text = pypdf.PdfReader(BytesIO(r.content)).pages[0].extract_text()
    for needle in (ids["invoice"]["invoice_number"], ids["po"]["po_number"], "Arden Supplies", "Acme Procurement", "1,69,500.00",
                   "15,255.00", "2,00,010.00", "Ergonomic chair"):
        assert needle in text, needle
    assert client.get(f"/invoices/{ids['invoice']['id']}/pdf").status_code == 401


def test_email_is_refused_clearly_when_not_configured(client):
    w = build_world(client)
    ids = lifecycle(client, w)
    r = client.post(f"/invoices/{ids['invoice']['id']}/email", headers=w["officer"], json={})
    assert r.status_code == 503 and "not configured" in r.json()["detail"]


def test_email_success_and_failure_are_recorded(client, monkeypatch):
    w = build_world(client)
    ids = lifecycle(client, w)
    url = f"/invoices/{ids['invoice']['id']}/email"
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "smtp_from", "billing@acme.test")
    monkeypatch.setattr(settings, "smtp_user", "user")
    monkeypatch.setattr(settings, "smtp_password", "secret")
    with mock.patch("smtplib.SMTP") as smtp:
        ok = client.post(url, headers=w["officer"], json={})
        server = smtp.return_value.__enter__.return_value
        msg = server.send_message.call_args[0][0]
    assert ok.status_code == 200 and ok.json()["ok"] and ok.json()["to"] == "arden@x.com"
    assert msg["To"] == "arden@x.com" and ids["invoice"]["invoice_number"] in msg["Subject"]
    assert [p.get_filename() for p in msg.iter_attachments()] == [f"{ids['invoice']['invoice_number']}.pdf"]
    server.starttls.assert_called_once()
    server.login.assert_called_once_with("user", "secret")
    with mock.patch("smtplib.SMTP", side_effect=OSError("connection refused")):
        bad = client.post(url, headers=w["officer"], json=dict(to="finance@x.com"))
    assert bad.status_code == 502 and "secret" not in bad.text and "connection refused" not in bad.text
    log = client.get(f"/invoices/{ids['invoice']['id']}", headers=w["officer"]).json()["emails"]
    assert [(e["to_email"], e["ok"]) for e in log] == [("arden@x.com", True), ("finance@x.com", False)]
    assert client.post(url, headers=w["officer"], json=dict(to="not-an-email")).status_code == 422
    assert client.post(url, headers=w["arden"], json={}).status_code == 403   # vendors cannot send invoices


def test_marking_paid(client):
    w = build_world(client)
    ids = lifecycle(client, w)
    url = f"/invoices/{ids['invoice']['id']}/mark-paid"
    assert client.patch(url, headers=w["officer"]).status_code == 403
    assert client.patch(url, headers=w["arden"]).status_code == 403
    r = client.patch(url, headers=w["mgr1"])
    assert r.status_code == 200 and r.json()["status"] == "paid" and r.json()["paid_at"]
    assert client.patch(url, headers=w["mgr1"]).status_code == 409
    assert client.get(f"/purchase-orders/{ids['po']['id']}", headers=w["officer"]).json()["status"] == "closed"