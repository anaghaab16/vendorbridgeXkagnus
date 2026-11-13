"""One test that walks the complete procurement lifecycle the way a reviewer would, checking every module along the way."""
from io import BytesIO
from unittest import mock

from pypdf import PdfReader

from app.config import settings
from .helpers import build_world, item_ids, make_rfq, quote, quotation_ids, STANDARD


def test_complete_procurement_lifecycle(client, monkeypatch):
    w = build_world(client)

    # 1 RFQ with an attachment, assigned to three vendors and sent
    rfq = make_rfq(client, w)
    assert client.post(f"/rfqs/{rfq['id']}/attachments", headers=w["officer"], files={"file": ("spec.pdf", b"%PDF-1.4")}).status_code == 201
    ids = item_ids(client, w, rfq["id"])
    assert all(len(client.get("/my/rfqs", headers=w[v]).json()) == 1 for v in ("arden", "kestrel", "maple"))

    # 2 vendors quote; one edits before the deadline
    for key, (prices, days, terms) in STANDARD.items():
        assert quote(client, w[key], rfq["id"], ids, prices, days=days, terms=terms).status_code == 200
    assert quote(client, w["kestrel"], rfq["id"], ids, [3700, 8000], days=14, terms="15 days").status_code == 200

    # 3 compare quotations
    cmp_ = client.get(f"/rfqs/{rfq['id']}/comparison", headers=w["officer"]).json()
    assert len(cmp_["quotes"]) == 3 and [q["vendor_name"] for q in cmp_["quotes"] if q["is_lowest"]] == ["Arden Supplies"]
    qid = quotation_ids(client, w, rfq["id"])["arden"]

    # 4 select, approve in two levels
    assert client.put(f"/rfqs/{rfq['id']}/selected-quotation", headers=w["officer"], json=dict(quotation_id=qid)).status_code == 200
    appr = client.post("/approvals", headers=w["officer"], json=dict(rfq_id=rfq["id"])).json()
    assert client.post(f"/approvals/{appr['id']}/decision", headers=w["mgr1"], json=dict(decision="approve", remarks="OK")).status_code == 200
    done = client.post(f"/approvals/{appr['id']}/decision", headers=w["mgr2"], json=dict(decision="approve", remarks="Budget available")).json()
    assert done["status"] == "approved"

    # 5 purchase order and invoice
    po = client.post("/purchase-orders", headers=w["officer"], json=dict(approval_id=appr["id"])).json()
    inv = client.post("/invoices", headers=w["officer"], json=dict(po_id=po["id"])).json()
    assert inv["totals"]["grand_total"] == po["totals"]["grand_total"] == 200010.0
    assert client.get(f"/rfqs/{rfq['id']}", headers=w["officer"]).json()["approval"]["po_number"] == po["po_number"]

    # 6 PDF, email (with a stand-in mail server) and payment
    pdf = client.get(f"/invoices/{inv['id']}/pdf", headers=w["arden"])
    assert inv["invoice_number"] in PdfReader(BytesIO(pdf.content)).pages[0].extract_text()
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "smtp_from", "billing@acme.test")
    with mock.patch("smtplib.SMTP") as smtp:
        assert client.post(f"/invoices/{inv['id']}/email", headers=w["officer"], json={}).json()["ok"] is True
        assert smtp.return_value.__enter__.return_value.send_message.called
    assert client.patch(f"/invoices/{inv['id']}/mark-paid", headers=w["mgr1"]).json()["status"] == "paid"

    # 7 notifications reached the right people
    assert client.get("/notifications/unread-count", headers=w["arden"]).json()["count"] >= 3   # RFQ, PO, invoice, paid
    assert client.get("/notifications/unread-count", headers=w["maple"]).json()["count"] == 1    # only the RFQ

    # 8 the audit trail has every step, in order, by the right people
    items = client.get("/activity?limit=200", headers=w["admin"]).json()["items"][::-1]
    order = [i["action"] for i in items if i["entity_label"] in (rfq["rfq_number"], po["po_number"], inv["invoice_number"])]
    sequence = ["rfq.created", "rfq.attachment_added", "quotation.submitted", "quotation.updated", "quotation.selected",
                "approval.submitted", "approval.l1_approved", "approval.approved", "po.created", "invoice.created",
                "invoice.emailed", "invoice.paid"]
    positions = [order.index(a) for a in sequence]
    assert positions == sorted(positions), order

    # 9 reports reflect the saved data, and the export opens
    r = client.get("/reports/summary", headers=w["admin"]).json()
    assert (r["kpis"]["total_spend"], r["kpis"]["paid_total"], r["kpis"]["quotations_submitted"]) == (200010.0, 200010.0, 3)
    assert client.get("/reports/export", headers=w["admin"], params={"kind": "purchase_orders"}).text.count("\n") == 2