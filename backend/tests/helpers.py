from datetime import date, timedelta

PASSWORD = "password123"
GST = {"Arden": "29ABCDE1234F1Z5", "Kestrel": "27BCDEF2345G1Z6", "Maple": "29CDEFG3456H1Z7", "Blue": "27HJKLM8901N1ZC"}


def register(client, email, role, first="Test"):
    r = client.post("/auth/register", json=dict(first_name=first, last_name="User", email=email, phone="+91 98765 43210",
                                                  role=role, country="India", password=PASSWORD))
    assert r.status_code == 201, r.text
    return r.json()


def login(client, email, password=PASSWORD):
    r = client.post("/auth/login", json=dict(email=email, password=password))
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def build_world(client):
    """An admin, an officer, two managers, three active vendors with login accounts and one blocked vendor."""
    w = {"users": {}}
    for key, email, role in [("admin", "admin@x.com", "admin"), ("officer", "officer@x.com", "procurement_officer"),
                             ("mgr1", "mgr1@x.com", "manager"), ("mgr2", "mgr2@x.com", "manager"),
                             ("arden", "arden@x.com", "vendor"), ("kestrel", "kestrel@x.com", "vendor"),
                             ("maple", "maple@x.com", "vendor")]:
        w["users"][key] = register(client, email, role, first=key.title())
        w[key] = login(client, email)
    w["vendors"] = {}
    for key, rating, status in [("arden", 4.5, "active"), ("kestrel", 3.8, "active"), ("maple", 4.1, "active")]:
        name = {"arden": "Arden", "kestrel": "Kestrel", "maple": "Maple"}[key]
        r = client.post("/vendors", headers=w["officer"], json=dict(
            name=f"{name} Supplies", email=f"{key}@x.com", rating=rating, status=status, gst_number=GST[name],
            category="Furniture", contact_no="+91 98450 10001"))
        assert r.status_code == 201, r.text
        w["vendors"][key] = r.json()["id"]
    r = client.post("/vendors", headers=w["officer"], json=dict(name="Blue Ocean", email="blue@x.com", status="blocked"))
    w["vendors"]["blue"] = r.json()["id"]
    return w


def rfq_body(w, days=5, send=True, vendors=("arden", "kestrel", "maple"), **over):
    body = dict(title="Office furniture Q2", category="Furniture", deadline=(date.today() + timedelta(days=days)).isoformat(),
                description="Deliver to Mysuru", send=send, vendor_ids=[w["vendors"][v] for v in vendors],
                items=[dict(item_name="Ergonomic chair", quantity=25, unit="pcs"), dict(item_name="Standing desk", quantity=10, unit="pcs")])
    body.update(over)
    return body


def make_rfq(client, w, **kw):
    r = client.post("/rfqs", headers=w["officer"], json=rfq_body(w, **kw))
    assert r.status_code == 201, r.text
    return r.json()


def item_ids(client, w, rfq_id):
    return [i["id"] for i in client.get(f"/rfqs/{rfq_id}", headers=w["officer"]).json()["items"]]


def quote(client, headers, rfq_id, ids, prices, days=7, gst=18, terms="30 days", submit=True, notes=None):
    return client.put(f"/my/rfqs/{rfq_id}/quotation", headers=headers, json=dict(
        items=[dict(rfq_item_id=i, unit_price=p) for i, p in zip(ids, prices)], gst_percent=gst, delivery_days=days,
        payment_terms=terms, notes=notes, submit=submit))


# the three standard quotations: totals 200010.00 / 206500.00 / 203845.00 (all with 18% GST)
STANDARD = {"arden": ([3500, 8200], 7, "30 days"), "kestrel": ([3800, 8000], 14, "15 days"), "maple": ([3550, 8400], 5, "45 days")}


def submit_standard_quotes(client, w, rfq_id, who=("arden", "kestrel", "maple")):
    ids = item_ids(client, w, rfq_id)
    for key in who:
        prices, days, terms = STANDARD[key]
        r = quote(client, w[key], rfq_id, ids, prices, days=days, terms=terms)
        assert r.status_code == 200, r.text
    return ids


def quotation_ids(client, w, rfq_id):
    cmp_ = client.get(f"/rfqs/{rfq_id}/comparison", headers=w["officer"]).json()
    return {q["vendor_name"].split()[0].lower(): q["quotation_id"] for q in cmp_["quotes"]}


def to_approved(client, w, rfq_id, vendor="arden"):
    """Select a quotation, submit it and give both approvals. Returns the approval id."""
    qid = quotation_ids(client, w, rfq_id)[vendor]
    assert client.put(f"/rfqs/{rfq_id}/selected-quotation", headers=w["officer"], json=dict(quotation_id=qid)).status_code == 200
    a = client.post("/approvals", headers=w["officer"], json=dict(rfq_id=rfq_id))
    assert a.status_code == 201, a.text
    aid = a.json()["id"]
    assert client.post(f"/approvals/{aid}/decision", headers=w["mgr1"], json=dict(decision="approve", remarks="Looks fine")).status_code == 200
    assert client.post(f"/approvals/{aid}/decision", headers=w["mgr2"], json=dict(decision="approve", remarks="Budget ok")).status_code == 200
    return aid


def lifecycle(client, w, vendor="arden"):
    """RFQ to invoice. Returns the ids."""
    rfq = make_rfq(client, w)
    submit_standard_quotes(client, w, rfq["id"])
    aid = to_approved(client, w, rfq["id"], vendor)
    po = client.post("/purchase-orders", headers=w["officer"], json=dict(approval_id=aid))
    assert po.status_code == 201, po.text
    inv = client.post("/invoices", headers=w["officer"], json=dict(po_id=po.json()["id"]))
    assert inv.status_code == 201, inv.text
    return dict(rfq=rfq, approval_id=aid, po=po.json(), invoice=inv.json())