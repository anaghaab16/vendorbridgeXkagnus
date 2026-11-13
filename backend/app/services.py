"""Shared helpers for the RFQ, quotation and document routes."""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ApprovalStatus, RFQ, Quotation, QuotationStatus, RFQVendor, User, Vendor

CENT = Decimal("0.01")


def D(x) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


def q2(x) -> Decimal:
    """Round to 2 decimals, half up (normal money rounding)."""
    return D(x).quantize(CENT, rounding=ROUND_HALF_UP)


def deadline_passed(rfq: RFQ) -> bool:
    return date.today() > rfq.deadline


def get_rfq_or_404(db: Session, rfq_id: int) -> RFQ:
    rfq = db.get(RFQ, rfq_id)
    if rfq is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "RFQ not found")
    return rfq


def vendor_for_user(db: Session, user: User) -> Vendor:
    """The vendor record whose email matches the logged-in vendor user."""
    vendor = db.scalar(select(Vendor).where(func.lower(Vendor.email) == user.email.lower()))
    if vendor is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "No vendor profile is linked to your email. Ask the procurement team to add your email to your vendor record.",
        )
    return vendor


def is_assigned(rfq: RFQ, vendor_id: int) -> bool:
    return any(rv.vendor_id == vendor_id for rv in rfq.vendors)


def item_out(it) -> dict:
    return {"id": it.id, "item_name": it.item_name, "quantity": it.quantity, "unit": it.unit}


def attachment_out(a) -> dict:
    return {"id": a.id, "file_name": a.file_name, "size": a.size, "uploaded_at": a.uploaded_at}


def quote_lines(q: Quotation) -> list[dict]:
    prices = {i.rfq_item_id: i.unit_price for i in q.items}
    lines = []
    for it in q.rfq.items:
        price = prices.get(it.id)
        lines.append({
            "rfq_item_id": it.id, "item_name": it.item_name, "quantity": it.quantity, "unit": it.unit,
            "unit_price": price,
            "line_total": None if price is None else float(q2(D(price) * D(it.quantity))),
        })
    return lines


def quote_totals(lines: list[dict], gst_percent: float) -> tuple[float, float, float]:
    subtotal = q2(sum((D(l["line_total"] or 0) for l in lines), Decimal(0)))
    gst = q2(subtotal * D(gst_percent) / 100)
    return float(subtotal), float(gst), float(subtotal + gst)


def doc_totals(rows: list[tuple], gst_percent: float, vendor_gst: str | None, buyer_gstin: str | None) -> dict:
    """Totals for a purchase order or invoice, from (unit_price, quantity) rows, using exact decimals.

    Tax is split into CGST + SGST for a same-state supply, or IGST when the first two digits
    (the state code) of the two GSTINs differ.
    """
    lines = [q2(D(price) * D(qty)) for price, qty in rows]
    subtotal = sum(lines, Decimal(0))
    gst_total = q2(subtotal * D(gst_percent) / 100)
    inter_state = bool(vendor_gst and buyer_gstin and vendor_gst[:2] != buyer_gstin[:2])
    if inter_state:
        cgst = sgst = Decimal("0.00")
        igst = gst_total
    else:
        cgst = q2(gst_total / 2)
        sgst = gst_total - cgst
        igst = Decimal("0.00")
    return {"lines": lines, "subtotal": subtotal, "cgst": cgst, "sgst": sgst, "igst": igst,
            "gst_total": gst_total, "grand_total": subtotal + gst_total}


def active_approval(rfq: RFQ):
    """The approval request that is still live (not rejected), if any."""
    return next((a for a in rfq.approvals if a.status != ApprovalStatus.rejected), None)


def approval_brief(rfq: RFQ) -> dict | None:
    a = active_approval(rfq)
    if a is None:
        return None
    po = a.purchase_order
    return {"id": a.id, "status": a.status, "po_id": po.id if po else None, "po_number": po.po_number if po else None}


def quotation_out(q: Quotation) -> dict:
    lines = quote_lines(q)
    subtotal, gst, total = quote_totals(lines, q.gst_percent)
    return {
        "id": q.id, "status": q.status, "gst_percent": q.gst_percent, "delivery_days": q.delivery_days,
        "payment_terms": q.payment_terms, "notes": q.notes, "submitted_at": q.submitted_at,
        "updated_at": q.updated_at, "lines": lines, "subtotal": subtotal, "gst_amount": gst, "total": total,
    }


def selected_quotation(rfq: RFQ) -> Quotation | None:
    return next((q for q in rfq.quotations if q.is_selected), None)


def rfq_summary(rfq: RFQ) -> dict:
    sel = selected_quotation(rfq)
    return {
        "id": rfq.id, "rfq_number": rfq.rfq_number, "title": rfq.title, "category": rfq.category, "deadline": rfq.deadline,
        "status": rfq.status, "created_at": rfq.created_at,
        "item_count": len(rfq.items), "vendor_count": len(rfq.vendors),
        "quote_count": sum(1 for q in rfq.quotations if q.status == QuotationStatus.submitted),
        "deadline_passed": deadline_passed(rfq),
        "selected_vendor_name": sel.vendor.name if sel else None,
    }


def rfq_detail(rfq: RFQ) -> dict:
    status_by_vendor = {q.vendor_id: q.status for q in rfq.quotations}
    return {
        **rfq_summary(rfq),
        "selected_quotation_id": getattr(selected_quotation(rfq), "id", None),
        "approval": approval_brief(rfq),
        "description": rfq.description,
        "items": [item_out(i) for i in rfq.items],
        "vendors": [
            {"vendor_id": rv.vendor_id, "name": rv.vendor.name, "rating": rv.vendor.rating,
             "email": rv.vendor.email, "quotation_status": status_by_vendor.get(rv.vendor_id)}
            for rv in rfq.vendors
        ],
        "attachments": [attachment_out(a) for a in rfq.attachments],
    }


def build_comparison(rfq: RFQ) -> dict:
    """Submitted quotations of one RFQ, side by side. Drafts are never included."""
    submitted = [q for q in rfq.quotations if q.status == QuotationStatus.submitted]
    columns = []
    for q in submitted:
        lines = quote_lines(q)
        subtotal, gst, total = quote_totals(lines, q.gst_percent)
        columns.append({
            "quotation_id": q.id, "vendor_id": q.vendor_id, "vendor_name": q.vendor.name, "rating": q.vendor.rating,
            "gst_percent": q.gst_percent, "delivery_days": q.delivery_days,
            "payment_terms": q.payment_terms, "notes": q.notes, "submitted_at": q.submitted_at,
            "lines": lines, "subtotal": subtotal, "gst_amount": gst, "total": total,
            "is_selected": q.is_selected,
        })
    lowest = min((c["total"] for c in columns), default=None)
    days = [c["delivery_days"] for c in columns if c["delivery_days"] is not None]
    fastest = min(days, default=None)
    for c in columns:
        c["is_lowest"] = c["total"] == lowest
        c["is_fastest"] = fastest is not None and c["delivery_days"] == fastest
    quoted = {q.vendor_id for q in submitted}
    return {
        "rfq_id": rfq.id, "rfq_number": rfq.rfq_number, "title": rfq.title, "deadline": rfq.deadline,
        "status": rfq.status, "selected_quotation_id": getattr(selected_quotation(rfq), "id", None),
        "approval": approval_brief(rfq),
        "items": [item_out(i) for i in rfq.items], "quotes": columns,
        "waiting": [rv.vendor.name for rv in rfq.vendors if rv.vendor_id not in quoted],
    }