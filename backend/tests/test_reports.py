from datetime import date, timedelta

import pytest

from .helpers import build_world, lifecycle, make_rfq, submit_standard_quotes


def summary(client, w, who="officer", **params):
    return client.get("/reports/summary", headers=w[who], params=params)


def test_empty_database_gives_zeros_not_errors(client):
    w = build_world(client)
    r = summary(client, w).json()
    assert r["has_data"] is False
    k = r["kpis"]
    assert k["po_count"] == 0 and k["total_spend"] == 0 and k["avg_approval_hours"] is None and k["avg_quotes_per_rfq"] == 0
    assert len(r["monthly"]) == 6 and all(m["pos"] == 0 and m["spend"] == 0 for m in r["monthly"])
    assert r["spend_by_category"] == [] and r["vendors"] == [] and r["definitions"]


def test_figures_match_the_saved_records(client):
    w = build_world(client)
    ids = lifecycle(client, w)
    r = summary(client, w).json()
    k = r["kpis"]
    assert r["has_data"] is True
    assert (k["rfqs_created"], k["rfqs_sent"], k["quotations_submitted"], k["avg_quotes_per_rfq"]) == (1, 1, 3, 3.0)
    assert (k["approvals_total"], k["approvals_approved"], k["approvals_rejected"], k["approvals_pending"]) == (1, 1, 0, 0)
    assert k["avg_approval_hours"] is not None and k["avg_approval_hours"] >= 0
    assert (k["po_count"], k["total_spend"], k["avg_po_value"]) == (1, 200010.0, 200010.0)
    assert (k["invoice_count"], k["invoiced_total"], k["paid_total"], k["outstanding_total"]) == (1, 200010.0, 0, 200010.0)
    assert k["overdue_count"] == 0
    client.patch(f"/invoices/{ids['invoice']['id']}/mark-paid", headers=w["mgr1"])
    k = summary(client, w).json()["kpis"]
    assert (k["paid_total"], k["outstanding_total"]) == (200010.0, 0)


def test_monthly_trend_and_categories(client):
    w = build_world(client)
    lifecycle(client, w)
    r = summary(client, w).json()
    this_month = date.today().strftime("%Y-%m")
    row = next(m for m in r["monthly"] if m["month"] == this_month)
    assert (row["rfqs"], row["pos"], row["spend"], row["invoiced"]) == (1, 1, 200010.0, 200010.0)
    assert r["monthly"][-1]["month"] == this_month and sum(m["spend"] for m in r["monthly"]) == 200010.0
    assert r["spend_by_category"] == [{"category": "Furniture", "spend": 200010.0, "po_count": 1}]


def test_vendor_performance_is_built_from_stored_data(client):
    w = build_world(client)
    lifecycle(client, w, vendor="arden")
    rows = {v["vendor"].split()[0]: v for v in summary(client, w).json()["vendors"]}
    a, k, m = rows["Arden"], rows["Kestrel"], rows["Maple"]
    assert (a["invited"], a["quoted"], a["response_rate"], a["lowest_wins"], a["po_count"], a["po_value"]) == (1, 1, 100.0, 1, 1, 200010.0)
    assert (a["avg_delivery_days"], a["rating"]) == (7.0, 4.5)
    assert (k["lowest_wins"], k["po_count"], k["avg_delivery_days"]) == (0, 0, 14.0)
    assert m["avg_delivery_days"] == 5.0
    assert list(rows)[0] == "Arden"   # sorted by PO value


def test_a_vendor_that_never_answers_has_a_zero_response_rate(client):
    w = build_world(client)
    rfq = make_rfq(client, w)
    submit_standard_quotes(client, w, rfq["id"], who=("arden",))
    rows = {v["vendor"].split()[0]: v for v in summary(client, w).json()["vendors"]}
    assert rows["Kestrel"]["response_rate"] == 0.0 and rows["Arden"]["response_rate"] == 100.0
    assert rows["Kestrel"]["avg_delivery_days"] is None


def test_date_range_filtering_and_validation(client):
    w = build_world(client)
    lifecycle(client, w)
    far = (date.today() - timedelta(days=400)).isoformat()
    older = summary(client, w, **{"from": far, "to": (date.today() - timedelta(days=300)).isoformat()}).json()
    assert older["has_data"] is False and older["kpis"]["po_count"] == 0
    wide = summary(client, w, **{"from": far}).json()
    assert wide["kpis"]["po_count"] == 1 and len(wide["monthly"]) >= 13
    assert summary(client, w, **{"from": "2026-12-31", "to": "2026-01-01"}).status_code == 422
    assert summary(client, w, **{"from": "2000-01-01"}).status_code == 422
    assert summary(client, w, **{"from": "not-a-date"}).status_code == 422


def test_report_access(client):
    w = build_world(client)
    for who in ("admin", "mgr1", "officer"):
        assert summary(client, w, who).status_code == 200
    assert summary(client, w, "arden").status_code == 403
    assert client.get("/reports/summary").status_code == 401


@pytest.mark.parametrize("kind,header,needle", [
    ("purchase_orders", "PO number,PO date,RFQ number,Vendor", "Arden Supplies"),
    ("invoices", "Invoice number,PO number,Vendor", "pending_payment"),
    ("vendor_performance", "Vendor,Rating,RFQs invited to", "Arden Supplies"),
    ("monthly", "Month,RFQs created,Purchase orders,Spend,Invoiced", date.today().strftime("%Y-%m")),
])
def test_csv_exports_open_and_contain_the_data(client, kind, header, needle):
    w = build_world(client)
    ids = lifecycle(client, w)
    r = client.get("/reports/export", headers=w["officer"], params={"kind": kind})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert ".csv" in r.headers["content-disposition"]
    lines = r.text.strip().splitlines()
    assert lines[0].startswith(header) and needle in r.text
    if kind == "purchase_orders":
        assert ids["po"]["po_number"] in lines[1] and "200010.0" in lines[1]
    import csv, io
    assert len(list(csv.reader(io.StringIO(r.text)))[0]) == len(list(csv.reader(io.StringIO(r.text)))[1])  # rectangular


def test_csv_export_is_safe_in_spreadsheets_and_validated(client):
    w = build_world(client)
    client.put(f"/vendors/{w['vendors']['maple']}", headers=w["officer"], json=dict(name='=HYPERLINK("http://evil")', email="maple@x.com", status="active"))
    lifecycle(client, w)
    text = client.get("/reports/export", headers=w["officer"], params={"kind": "vendor_performance"}).text
    assert "'=HYPERLINK" in text and "\n=HYPERLINK" not in text
    assert client.get("/reports/export", headers=w["officer"], params={"kind": "everything"}).status_code == 422
    assert client.get("/reports/export", headers=w["arden"], params={"kind": "monthly"}).status_code == 403
    assert client.get("/reports/export", headers=w["officer"], params={"kind": "invoices", "from": "2030-01-01", "to": "2029-01-01"}).status_code == 422
    empty = client.get("/reports/export", headers=w["officer"], params={"kind": "purchase_orders", "from": "2001-01-01", "to": "2001-02-01"})
    assert empty.status_code == 200 and len(empty.text.strip().splitlines()) == 1   # header only