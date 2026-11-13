"""Loads a small demo data set through the public API, so every rule in the app is applied to it.

    python scripts/seed_demo.py --api http://127.0.0.1:8000 --password "Demo@12345"

Use it on an empty demo database only. It creates demo accounts, vendors, RFQs, quotations and walks one RFQ
all the way to a paid invoice, so notifications, the audit log and the reports have real records to show.
"""
import argparse
import sys
from datetime import date, timedelta

import httpx

ap = argparse.ArgumentParser()
ap.add_argument("--api", default="http://127.0.0.1:8000")
ap.add_argument("--password", required=True, help="password given to every demo account (8+ characters)")
ap.add_argument("--force", action="store_true", help="run even if RFQs already exist")
args = ap.parse_args()
http = httpx.Client(base_url=args.api, timeout=30)


def call(method, path, token=None, expect=(200, 201, 204), **kw):
    r = http.request(method, path, headers={"Authorization": f"Bearer {token}"} if token else None, **kw)
    if r.status_code not in expect:
        sys.exit(f"{method} {path} failed with {r.status_code}: {r.text[:300]}")
    return r.json() if r.content and r.headers.get("content-type", "").startswith("application/json") else None


def account(first, email, role):
    r = http.post("/auth/register", json=dict(first_name=first, last_name="Demo", email=email, phone="+91 98450 20000",
                                              role=role, country="India", password=args.password))
    if r.status_code not in (201, 409):
        sys.exit(f"could not create {email}: {r.status_code} {r.text[:200]}")
    login = http.post("/auth/login", json=dict(email=email, password=args.password))
    if login.status_code != 200:
        sys.exit(f"{email} exists but the password does not match. Use the password you first created it with.")
    return login.json()["access_token"]


print("Accounts")
officer = account("Ana", "officer@example.com", "procurement_officer")
mgr1 = account("Meera", "manager1@example.com", "manager")
mgr2 = account("Manoj", "manager2@example.com", "manager")
vendor_accounts = {"arden": account("Arden", "arden.vendor@example.com", "vendor"),
                   "kestrel": account("Kestrel", "kestrel.vendor@example.com", "vendor"),
                   "maple": account("Maple", "maple.vendor@example.com", "vendor")}

if call("GET", "/rfqs", officer) and not args.force:
    sys.exit("RFQs already exist. This script is for an empty demo database. Use --force to add more anyway.")

print("Vendors")
V = [("Arden Packaging", "Packaging", "29ABCDE1234F1Z5", "arden.vendor@example.com", 4.5, "active"),
     ("Kestrel Logistics", "Logistics", "27BCDEF2345G1Z6", "kestrel.vendor@example.com", 3.8, "active"),
     ("Maple & Co. Stationery", "Stationery", "29CDEFG3456H1Z7", "maple.vendor@example.com", 4.1, "active"),
     ("Northwind Furniture", "Furniture", "33DEFGH4567J1Z8", "northwind.vendor@example.com", 4.8, "active"),
     ("TechCore Ltd", "IT Hardware", "29EFGHJ5678K1Z9", "techcore.vendor@example.com", 4.2, "active"),
     ("Infra Supplies Pvt Ltd", "Construction", "07FGHJK6789L1ZA", "infra.vendor@example.com", 0, "pending"),
     ("Sunrise Electricals", "Electrical", "29GHJKL7890M1ZB", "sunrise.vendor@example.com", 0, "pending"),
     ("Blue Ocean Traders", "Packaging", "27HJKLM8901N1ZC", "blueocean.vendor@example.com", 2.1, "blocked")]
vid = {}
existing = {v["email"]: v["id"] for v in call("GET", "/vendors", officer)}
for i, (name, cat, gst, email, rating, st) in enumerate(V):
    if email in existing:
        vid[name.split()[0].lower()] = existing[email]
        continue
    vid[name.split()[0].lower()] = call("POST", "/vendors", officer, json=dict(
        name=name, category=cat, gst_number=gst, contact_no=f"+91 98450 1000{i + 1}", email=email, rating=rating, status=st))["id"]

due = lambda d: (date.today() + timedelta(days=d)).isoformat()


def rfq(title, category, days, items, vendors, send=True):
    r = call("POST", "/rfqs", officer, json=dict(title=title, category=category, deadline=due(days), description="Demo RFQ",
                                                 items=[dict(item_name=n, quantity=q, unit=u) for n, q, u in items],
                                                 vendor_ids=[vid[v] for v in vendors], send=send))
    r["item_ids"] = [i["id"] for i in call("GET", f"/rfqs/{r['id']}", officer)["items"]]
    return r


def quote(rfq_, who, prices, days, terms, gst=18):
    call("PUT", f"/my/rfqs/{rfq_['id']}/quotation", vendor_accounts[who], json=dict(
        items=[dict(rfq_item_id=i, unit_price=p) for i, p in zip(rfq_["item_ids"], prices)], gst_percent=gst,
        delivery_days=days, payment_terms=terms, submit=True))


def qid(rfq_, name):
    cmp_ = call("GET", f"/rfqs/{rfq_['id']}/comparison", officer)
    return next(q["quotation_id"] for q in cmp_["quotes"] if q["vendor_name"].lower().startswith(name))


def select_and_submit(rfq_, name):
    call("PUT", f"/rfqs/{rfq_['id']}/selected-quotation", officer, json=dict(quotation_id=qid(rfq_, name)))
    return call("POST", "/approvals", officer, json=dict(rfq_id=rfq_["id"]))["id"]


print("RFQs and quotations")
A = rfq("Office furniture procurement Q2", "Furniture", 13, [("Ergonomic chair", 25, "pcs"), ("Standing desk", 10, "pcs")], ["arden", "kestrel", "maple"])
quote(A, "arden", [3500, 8200], 7, "30 days"); quote(A, "kestrel", [3800, 8000], 14, "15 days"); quote(A, "maple", [3550, 8400], 5, "45 days")
B = rfq("Laptops for new hires", "IT Hardware", 16, [("Laptop", 15, "pcs"), ("Laptop bag", 15, "pcs"), ("Wireless mouse", 15, "pcs")], ["arden", "kestrel", "maple"])
quote(B, "arden", [52000, 800, 450], 12, "30 days"); quote(B, "kestrel", [49500, 900, 400], 20, "30 days"); quote(B, "maple", [51000, 750, 500], 8, "45 days")
C = rfq("Packaging material restock", "Packaging", 11, [("Corrugated box", 500, "pcs"), ("Bubble wrap roll", 40, "rolls"), ("Packing tape", 120, "rolls")], ["arden", "kestrel"])
quote(C, "kestrel", [20, 600, 40], 9, "30 days")
rfq("Office stationery refill", "Stationery", 20, [("Notebook", 200, "pcs"), ("Ball pens", 50, "boxes"), ("A4 paper", 100, "reams")], ["arden", "maple"])
rfq("Network cables and routers", "IT Hardware", 27, [("Cat6 cable", 20, "rolls"), ("Router", 5, "pcs")], [], send=False)

print("Approvals, purchase order, invoice")
a = select_and_submit(A, "arden")                       # RFQ A goes all the way to a paid invoice
call("POST", f"/approvals/{a}/decision", mgr1, json=dict(decision="approve", remarks="Quotation is within budget"))
call("POST", f"/approvals/{a}/decision", mgr2, json=dict(decision="approve", remarks="Approved for purchase"))
po = call("POST", "/purchase-orders", officer, json=dict(approval_id=a))
inv = call("POST", "/invoices", officer, json=dict(po_id=po["id"]))
call("PATCH", f"/invoices/{inv['id']}/mark-paid", mgr1)
b = select_and_submit(B, "kestrel")                     # RFQ B: approved, PO and invoice created, invoice left unpaid (IGST case)
call("POST", f"/approvals/{b}/decision", mgr1, json=dict(decision="approve"))
call("POST", f"/approvals/{b}/decision", mgr2, json=dict(decision="approve", remarks="Cheapest laptops"))
po2 = call("POST", "/purchase-orders", officer, json=dict(approval_id=b))
call("POST", "/invoices", officer, json=dict(po_id=po2["id"]))
c = select_and_submit(C, "kestrel")                     # RFQ C: rejected at the first level
call("POST", f"/approvals/{c}/decision", mgr1, json=dict(decision="reject", remarks="Price needs a revision"))

print(f"\nDone. Sign in at the app with password {args.password!r}:")
for email, role in [("officer@example.com", "procurement officer"), ("manager1@example.com", "manager (L1 approver)"),
                    ("manager2@example.com", "manager (L2 approver)"), ("arden.vendor@example.com", "vendor"),
                    ("kestrel.vendor@example.com", "vendor"), ("maple.vendor@example.com", "vendor")]:
    print(f"  {email:30} {role}")