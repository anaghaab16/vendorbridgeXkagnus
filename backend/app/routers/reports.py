import csv
import io
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import (
    ApprovalRequest, ApprovalStatus, Invoice, InvoiceStatus, PurchaseOrder, Quotation, QuotationStatus,
    RFQ, RFQStatus, RFQVendor, Role, Vendor,
)
from app.services import quote_lines, quote_totals

router = APIRouter(prefix="/reports", tags=["reports"])
REPORT_ROLES = (Role.admin, Role.manager, Role.procurement_officer)
MAX_DAYS = 5 * 366

DEFINITIONS = {
    "Total spend": "Sum of purchase order grand totals (including GST) with a PO date inside the range.",
    "Invoiced": "Sum of invoice grand totals with an invoice date inside the range.",
    "Paid": "Part of the invoiced amount whose invoices are marked paid.",
    "Outstanding": "Part of the invoiced amount whose invoices are not yet paid.",
    "Overdue": "Outstanding invoices whose due date is before today.",
    "Approval turnaround": "Average hours from submission to final approval, for requests submitted in the range and approved.",
    "Response rate": "Submitted quotations divided by RFQs sent to the vendor (RFQs created in the range, status sent or closed).",
    "Lowest-price wins": "Number of RFQs with two or more submitted quotations where this vendor had the lowest total.",
    "Average delivery": "Mean promised delivery time, in days, of the vendor's submitted quotations.",
    "Monthly trend": "Counts and amounts grouped by calendar month (UTC) of the RFQ creation date, PO date and invoice date.",
}


def parse_range(from_date: date | None, to_date: date | None) -> tuple[date, date]:
    end = to_date or date.today()
    if from_date is None:  # default: the last 6 calendar months
        month = end.month - 5
        year = end.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        start = date(year, month, 1)
    else:
        start = from_date
    if start > end:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The start date must be on or before the end date")
    if (end - start).days > MAX_DAYS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose a range of five years or less")
    return start, end


def months_between(start: date, end: date) -> list[str]:
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def month_label(key: str) -> str:
    return datetime.strptime(key, "%Y-%m").strftime("%b %Y")


def money(x) -> float:
    return round(float(x or 0), 2)


def compute(db: Session, start: date, end: date) -> dict:
    lo = datetime.combine(start, time.min)
    hi = datetime.combine(end + timedelta(days=1), time.min)
    today = date.today()

    rfqs = db.scalars(select(RFQ).where(RFQ.created_at >= lo, RFQ.created_at < hi)).all()
    pos = db.scalars(select(PurchaseOrder).where(PurchaseOrder.po_date >= start, PurchaseOrder.po_date <= end)).all()
    invoices = db.scalars(select(Invoice).where(Invoice.invoice_date >= start, Invoice.invoice_date <= end)).all()
    approvals = db.scalars(select(ApprovalRequest).where(ApprovalRequest.created_at >= lo, ApprovalRequest.created_at < hi)).all()

    live_rfqs = [r for r in rfqs if r.status in (RFQStatus.sent, RFQStatus.closed)]
    submitted = [q for r in live_rfqs for q in r.quotations if q.status == QuotationStatus.submitted]

    approved = [a for a in approvals if a.status == ApprovalStatus.approved and a.completed_at]
    hours = [(a.completed_at - a.created_at).total_seconds() / 3600 for a in approved]

    invoiced = sum(float(i.grand_total) for i in invoices)
    paid = sum(float(i.grand_total) for i in invoices if i.status == InvoiceStatus.paid)
    overdue = [i for i in invoices if i.status == InvoiceStatus.pending_payment and i.due_date < today]
    spend = sum(float(p.grand_total) for p in pos)

    kpis = {
        "rfqs_created": len(rfqs), "rfqs_sent": len(live_rfqs), "quotations_submitted": len(submitted),
        "avg_quotes_per_rfq": round(len(submitted) / len(live_rfqs), 2) if live_rfqs else 0,
        "approvals_total": len(approvals),
        "approvals_approved": sum(1 for a in approvals if a.status == ApprovalStatus.approved),
        "approvals_rejected": sum(1 for a in approvals if a.status == ApprovalStatus.rejected),
        "approvals_pending": sum(1 for a in approvals if a.status in (ApprovalStatus.awaiting_l1, ApprovalStatus.awaiting_l2)),
        "avg_approval_hours": round(sum(hours) / len(hours), 2) if hours else None,
        "po_count": len(pos), "total_spend": money(spend), "avg_po_value": money(spend / len(pos)) if pos else 0,
        "invoice_count": len(invoices), "invoiced_total": money(invoiced), "paid_total": money(paid),
        "outstanding_total": money(invoiced - paid), "overdue_total": money(sum(float(i.grand_total) for i in overdue)),
        "overdue_count": len(overdue),
    }

    monthly = {k: {"month": k, "label": month_label(k), "rfqs": 0, "pos": 0, "spend": 0.0, "invoiced": 0.0}
               for k in months_between(start, end)}
    for r in rfqs:
        monthly[r.created_at.strftime("%Y-%m")]["rfqs"] += 1
    for p in pos:
        row = monthly[p.po_date.strftime("%Y-%m")]
        row["pos"] += 1
        row["spend"] += float(p.grand_total)
    for i in invoices:
        monthly[i.invoice_date.strftime("%Y-%m")]["invoiced"] += float(i.grand_total)
    for row in monthly.values():
        row["spend"], row["invoiced"] = money(row["spend"]), money(row["invoiced"])

    by_cat = defaultdict(lambda: {"spend": 0.0, "po_count": 0})
    for p in pos:
        c = by_cat[p.rfq.category]
        c["spend"] += float(p.grand_total)
        c["po_count"] += 1
    categories = sorted(({"category": k, "spend": money(v["spend"]), "po_count": v["po_count"]} for k, v in by_cat.items()),
                        key=lambda x: -x["spend"])

    # vendor performance
    perf: dict[int, dict] = {}

    def row(v: Vendor) -> dict:
        return perf.setdefault(v.id, {"vendor_id": v.id, "vendor": v.name, "rating": v.rating, "invited": 0, "quoted": 0,
                                      "lowest_wins": 0, "po_count": 0, "po_value": 0.0, "_days": []})
    for r in live_rfqs:
        for rv in r.vendors:
            row(rv.vendor)["invited"] += 1
    for r in live_rfqs:
        subs = [q for q in r.quotations if q.status == QuotationStatus.submitted]
        totals = {}
        for q in subs:
            totals[q.id] = quote_totals(quote_lines(q), q.gst_percent)[2]
            d = row(q.vendor)
            d["quoted"] += 1
            if q.delivery_days:
                d["_days"].append(q.delivery_days)
        if len(subs) >= 2:
            best = min(totals.values())
            for q in subs:
                if totals[q.id] == best:
                    row(q.vendor)["lowest_wins"] += 1
    for p in pos:
        d = row(p.vendor)
        d["po_count"] += 1
        d["po_value"] += float(p.grand_total)
    vendors = []
    for d in perf.values():
        days = d.pop("_days")
        d["response_rate"] = round(d["quoted"] / d["invited"] * 100, 1) if d["invited"] else None
        d["avg_delivery_days"] = round(sum(days) / len(days), 1) if days else None
        d["po_value"] = money(d["po_value"])
        vendors.append(d)
    vendors.sort(key=lambda d: (-d["po_value"], -d["quoted"], d["vendor"]))

    return {"range": {"from": start.isoformat(), "to": end.isoformat()}, "kpis": kpis, "monthly": list(monthly.values()),
            "spend_by_category": categories, "vendors": vendors, "definitions": DEFINITIONS,
            "has_data": bool(rfqs or pos or invoices or approvals)}


@router.get("/summary")
def summary(from_date: date | None = Query(None, alias="from"), to_date: date | None = Query(None, alias="to"),
            db: Session = Depends(get_db), _=Depends(require_roles(*REPORT_ROLES))):
    start, end = parse_range(from_date, to_date)
    return compute(db, start, end)


def safe(cell):
    """Stop spreadsheet programs from running a cell that starts like a formula."""
    if isinstance(cell, str) and cell[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + cell
    return cell


@router.get("/export")
def export(kind: str = Query(..., pattern="^(purchase_orders|invoices|vendor_performance|monthly)$"),
           from_date: date | None = Query(None, alias="from"), to_date: date | None = Query(None, alias="to"),
           db: Session = Depends(get_db), _=Depends(require_roles(*REPORT_ROLES))):
    start, end = parse_range(from_date, to_date)
    out = io.StringIO()
    w = csv.writer(out)
    if kind == "purchase_orders":
        w.writerow(["PO number", "PO date", "RFQ number", "Vendor", "Status", "Subtotal", "CGST", "SGST", "IGST", "Grand total"])
        for p in db.scalars(select(PurchaseOrder).where(PurchaseOrder.po_date >= start, PurchaseOrder.po_date <= end)
                            .order_by(PurchaseOrder.po_date, PurchaseOrder.id)):
            w.writerow([safe(x) for x in [p.po_number, p.po_date, p.rfq.rfq_number, p.vendor_name, p.status.value,
                        money(p.subtotal), money(p.cgst), money(p.sgst), money(p.igst), money(p.grand_total)]])
    elif kind == "invoices":
        w.writerow(["Invoice number", "PO number", "Vendor", "Invoice date", "Due date", "Status", "Subtotal", "GST total", "Grand total", "Paid at"])
        for i in db.scalars(select(Invoice).where(Invoice.invoice_date >= start, Invoice.invoice_date <= end)
                            .order_by(Invoice.invoice_date, Invoice.id)):
            w.writerow([safe(x) for x in [i.invoice_number, i.po.po_number, i.po.vendor_name, i.invoice_date, i.due_date,
                        i.status.value, money(i.subtotal), money(i.gst_total), money(i.grand_total),
                        i.paid_at.isoformat() if i.paid_at else ""]])
    elif kind == "vendor_performance":
        w.writerow(["Vendor", "Rating", "RFQs invited to", "Quotations submitted", "Response rate %", "Lowest-price wins",
                    "Average delivery days", "Purchase orders", "PO value"])
        for d in compute(db, start, end)["vendors"]:
            w.writerow([safe(x) for x in [d["vendor"], d["rating"], d["invited"], d["quoted"], d["response_rate"],
                        d["lowest_wins"], d["avg_delivery_days"], d["po_count"], d["po_value"]]])
    else:
        w.writerow(["Month", "RFQs created", "Purchase orders", "Spend", "Invoiced"])
        for m in compute(db, start, end)["monthly"]:
            w.writerow([m["month"], m["rfqs"], m["pos"], m["spend"], m["invoiced"]])
    name = f"vendorbridge-{kind.replace('_', '-')}-{start}-to-{end}.csv"
    return Response(out.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})