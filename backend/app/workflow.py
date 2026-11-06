"""Approval, purchase order and invoice logic. Every figure here is read from the database, never from the browser."""
import re
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    ApprovalRequest, ApprovalStatus, ApprovalStep, Invoice, InvoiceStatus, POItem, POStatus,
    PurchaseOrder, RFQStatus, Role, StepStatus, User, Vendor,
)
from app.services import (
    D, active_approval, doc_totals, get_rfq_or_404, quote_lines, quote_totals, selected_quotation,
    vendor_for_user,
)

APPROVER_ROLES = (Role.admin, Role.manager)
STAFF_ROLES = (Role.admin, Role.manager, Role.procurement_officer)
LEVEL_LABEL = {1: "L1 review", 2: "L2 approval"}


def now():
    return datetime.now(timezone.utc)


# ------------------------------------------------------------- approvals

def submit_for_approval(db: Session, rfq_id: int, user: User) -> ApprovalRequest:
    rfq = get_rfq_or_404(db, rfq_id)
    if rfq.status not in (RFQStatus.sent, RFQStatus.closed):
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a sent or closed RFQ can go for approval")
    quote = selected_quotation(rfq)
    if quote is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Select a quotation on the comparison screen first")
    if active_approval(rfq) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This RFQ already has an approval request")
    req = ApprovalRequest(rfq_id=rfq.id, quotation_id=quote.id, requested_by=user.id,
                          status=ApprovalStatus.awaiting_l1)
    req.steps = [ApprovalStep(level=1), ApprovalStep(level=2)]
    db.add(req)
    try:
        db.commit()
    except IntegrityError:  # two people submitted at the same moment
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This RFQ already has an approval request")
    db.refresh(req)
    return req


def decision_state(req: ApprovalRequest, user: User) -> tuple[bool, str | None, int]:
    """Can this user decide on the request right now? Returns (allowed, reason, http status if not)."""
    if req.status not in (ApprovalStatus.awaiting_l1, ApprovalStatus.awaiting_l2):
        return False, f"This request is already {req.status.value}", status.HTTP_409_CONFLICT
    if user.role not in APPROVER_ROLES:
        return False, "Only managers and admins can approve or reject", status.HTTP_403_FORBIDDEN
    if user.id == req.requested_by:
        return False, "You submitted this request, so someone else must decide on it", status.HTTP_403_FORBIDDEN
    if req.status == ApprovalStatus.awaiting_l2 and req.steps[0].approver_id == user.id:
        return False, "A different approver must give the second approval", status.HTTP_403_FORBIDDEN
    return True, None, 200


def decide(db: Session, req: ApprovalRequest, user: User, approve: bool, remarks: str | None) -> ApprovalRequest:
    allowed, reason, code = decision_state(req, user)
    if not allowed:
        raise HTTPException(code, reason)
    if not approve and (remarks is None or len(remarks) < 5):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter remarks (at least 5 characters) to reject")
    level = 1 if req.status == ApprovalStatus.awaiting_l1 else 2
    step = req.steps[level - 1]
    step.status = StepStatus.approved if approve else StepStatus.rejected
    step.approver_id = user.id
    step.remarks = remarks
    step.acted_at = now()
    if not approve:
        req.status = ApprovalStatus.rejected
        req.completed_at = step.acted_at
    elif level == 1:
        req.status = ApprovalStatus.awaiting_l2
    else:
        req.status = ApprovalStatus.approved
        req.completed_at = step.acted_at
    db.commit()
    db.refresh(req)
    return req


def approval_timeline(req: ApprovalRequest) -> list[dict]:
    events = [{"key": "submitted", "label": "Submitted", "status": "done", "actor": req.requester.name,
               "at": req.created_at, "remarks": None}]
    for step in req.steps:
        if step.status == StepStatus.approved:
            st = "done"
        elif step.status == StepStatus.rejected:
            st = "rejected"
        elif req.status == ApprovalStatus.rejected:
            st = "skipped"
        else:
            current = (req.status == ApprovalStatus.awaiting_l1 and step.level == 1) or \
                      (req.status == ApprovalStatus.awaiting_l2 and step.level == 2)
            st = "current" if current else "pending"
        events.append({"key": f"l{step.level}", "label": LEVEL_LABEL[step.level], "status": st,
                       "actor": step.approver.name if step.approver else None,
                       "at": step.acted_at, "remarks": step.remarks})
    po = req.purchase_order
    if po:
        st = "done"
    elif req.status == ApprovalStatus.approved:
        st = "current"
    elif req.status == ApprovalStatus.rejected:
        st = "skipped"
    else:
        st = "pending"
    events.append({"key": "po", "label": "Generate PO", "status": st,
                   "actor": po.creator.name if po else None, "at": po.created_at if po else None,
                   "remarks": po.po_number if po else None})
    return events


def step_label(req: ApprovalRequest) -> str:
    return {ApprovalStatus.awaiting_l1: "Awaiting L1 review", ApprovalStatus.awaiting_l2: "Awaiting L2 approval",
            ApprovalStatus.approved: "Approved", ApprovalStatus.rejected: "Rejected"}[req.status]


def quote_column(q) -> dict:
    lines = quote_lines(q)
    subtotal, gst, total = quote_totals(lines, q.gst_percent)
    return {"quotation_id": q.id, "vendor_id": q.vendor_id, "vendor_name": q.vendor.name, "rating": q.vendor.rating,
            "gst_percent": q.gst_percent, "delivery_days": q.delivery_days, "payment_terms": q.payment_terms,
            "notes": q.notes, "submitted_at": q.submitted_at, "lines": lines, "subtotal": subtotal,
            "gst_amount": gst, "total": total, "is_lowest": False, "is_fastest": False, "is_selected": q.is_selected}


def approval_list_row(req: ApprovalRequest) -> dict:
    col = quote_column(req.quotation)
    po = req.purchase_order
    return {"id": req.id, "rfq_id": req.rfq_id, "rfq_number": req.rfq.rfq_number, "rfq_title": req.rfq.title,
            "vendor_name": col["vendor_name"], "total": col["total"], "status": req.status,
            "step_label": step_label(req), "requested_by_name": req.requester.name, "created_at": req.created_at,
            "completed_at": req.completed_at, "po_id": po.id if po else None, "po_number": po.po_number if po else None}


def approval_detail(req: ApprovalRequest, user: User) -> dict:
    allowed, reason, _ = decision_state(req, user)
    return {**approval_list_row(req), "quotation": quote_column(req.quotation),
            "timeline": approval_timeline(req), "can_decide": allowed,
            "decision_note": None if allowed else reason}


# -------------------------------------------------------- purchase orders

def generate_po(db: Session, approval_id: int, user: User) -> PurchaseOrder:
    req = db.get(ApprovalRequest, approval_id, with_for_update=True)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Approval request not found")
    if req.status != ApprovalStatus.approved:
        raise HTTPException(status.HTTP_409_CONFLICT, "A purchase order can only be created from an approved quotation")
    if req.purchase_order is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{req.purchase_order.po_number} was already created for this approval")

    quote = req.quotation
    rfq, vendor = quote.rfq, quote.vendor
    prices = {i.rfq_item_id: i.unit_price for i in quote.items}
    if any(it.id not in prices for it in rfq.items):
        raise HTTPException(status.HTTP_409_CONFLICT, "The quotation does not price every item")
    rows = [(prices[it.id], it.quantity) for it in rfq.items]
    totals = doc_totals(rows, quote.gst_percent, vendor.gst_number, settings.company_gstin or None)

    po = PurchaseOrder(
        approval_id=req.id, quotation_id=quote.id, rfq_id=rfq.id, vendor_id=vendor.id, po_date=date.today(),
        payment_terms=quote.payment_terms, delivery_days=quote.delivery_days, gst_percent=quote.gst_percent,
        subtotal=totals["subtotal"], cgst=totals["cgst"], sgst=totals["sgst"], igst=totals["igst"],
        gst_total=totals["gst_total"], grand_total=totals["grand_total"],
        vendor_name=vendor.name, vendor_gst=vendor.gst_number, vendor_contact=vendor.contact_no, vendor_email=vendor.email,
        buyer_name=settings.company_name, buyer_address=settings.company_address or None,
        buyer_gstin=settings.company_gstin or None, created_by=user.id,
    )
    po.items = [POItem(item_name=it.item_name, unit=it.unit, quantity=it.quantity,
                       unit_price=D(prices[it.id]), line_total=totals["lines"][n])
                for n, it in enumerate(rfq.items)]
    db.add(po)
    try:
        db.flush()
        po.po_number = f"PO-{date.today().year}-{po.id:04d}"
        db.commit()
    except IntegrityError:  # someone else created it a moment earlier
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A purchase order already exists for this approval")
    db.refresh(po)
    return po


# ---------------------------------------------------------------- invoices

def payment_days(terms: str | None) -> int:
    m = re.search(r"(\d{1,3})\s*days?", terms or "", re.I)
    return min(int(m.group(1)), 365) if m else 30


def generate_invoice(db: Session, po_id: int, user: User) -> Invoice:
    po = db.get(PurchaseOrder, po_id, with_for_update=True)
    if po is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Purchase order not found")
    if po.approval.status != ApprovalStatus.approved or po.status != POStatus.issued:
        raise HTTPException(status.HTTP_409_CONFLICT, "An invoice can only be created from an issued purchase order")
    if po.invoice is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{po.invoice.invoice_number} was already created for this purchase order")
    totals = doc_totals([(i.unit_price, i.quantity) for i in po.items], po.gst_percent, po.vendor_gst, po.buyer_gstin)
    if totals["grand_total"] != po.grand_total:  # the stored PO and a fresh calculation must agree
        raise HTTPException(status.HTTP_409_CONFLICT, "The purchase order totals do not match its items")
    today = date.today()
    inv = Invoice(po_id=po.id, invoice_date=today, due_date=today + timedelta(days=payment_days(po.payment_terms)),
                  subtotal=totals["subtotal"], cgst=totals["cgst"], sgst=totals["sgst"], igst=totals["igst"],
                  gst_total=totals["gst_total"], grand_total=totals["grand_total"], created_by=user.id)
    db.add(inv)
    try:
        db.flush()
        inv.invoice_number = f"INV-{today.year}-{inv.id:04d}"
        po.status = POStatus.invoiced
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An invoice already exists for this purchase order")
    db.refresh(inv)
    return inv


def mark_paid(db: Session, inv: Invoice) -> Invoice:
    if inv.status == InvoiceStatus.paid:
        raise HTTPException(status.HTTP_409_CONFLICT, "This invoice is already paid")
    inv.status = InvoiceStatus.paid
    inv.paid_at = now()
    inv.po.status = POStatus.closed
    db.commit()
    db.refresh(inv)
    return inv


# ---------------------------------------------------------- output builders

def tax_label(t) -> str:
    return "IGST" if t.igst and t.igst > 0 else "CGST + SGST"


def parties(po: PurchaseOrder) -> tuple[dict, dict]:
    buyer = {"name": po.buyer_name, "address": po.buyer_address, "gstin": po.buyer_gstin}
    vendor = {"name": po.vendor_name, "gstin": po.vendor_gst, "contact": po.vendor_contact, "email": po.vendor_email}
    return buyer, vendor


def doc_items(po: PurchaseOrder) -> list[dict]:
    return [{"item_name": i.item_name, "unit": i.unit, "quantity": i.quantity, "unit_price": float(i.unit_price),
             "line_total": float(i.line_total)} for i in po.items]


def doc_totals_out(doc, gst_percent: float) -> dict:
    return {"subtotal": float(doc.subtotal), "cgst": float(doc.cgst), "sgst": float(doc.sgst), "igst": float(doc.igst),
            "gst_total": float(doc.gst_total), "gst_percent": gst_percent, "grand_total": float(doc.grand_total),
            "tax_label": tax_label(doc)}


def po_list_row(po: PurchaseOrder) -> dict:
    inv = po.invoice
    return {"id": po.id, "po_number": po.po_number, "rfq_id": po.rfq_id, "rfq_number": po.rfq.rfq_number,
            "rfq_title": po.rfq.title, "vendor_name": po.vendor_name, "po_date": po.po_date, "status": po.status,
            "grand_total": float(po.grand_total), "invoice_id": inv.id if inv else None,
            "invoice_number": inv.invoice_number if inv else None}


def po_detail(po: PurchaseOrder) -> dict:
    buyer, vendor = parties(po)
    return {**po_list_row(po), "approval_id": po.approval_id, "quotation_id": po.quotation_id,
            "payment_terms": po.payment_terms, "delivery_days": po.delivery_days, "buyer": buyer, "vendor": vendor,
            "items": doc_items(po), "totals": doc_totals_out(po, po.gst_percent),
            "created_by_name": po.creator.name, "created_at": po.created_at}


def invoice_list_row(inv: Invoice) -> dict:
    po = inv.po
    return {"id": inv.id, "invoice_number": inv.invoice_number, "po_id": po.id, "po_number": po.po_number,
            "vendor_name": po.vendor_name, "invoice_date": inv.invoice_date, "due_date": inv.due_date,
            "status": inv.status, "is_overdue": inv.status == InvoiceStatus.pending_payment and date.today() > inv.due_date,
            "grand_total": float(inv.grand_total)}


def invoice_detail(inv: Invoice) -> dict:
    po = inv.po
    buyer, vendor = parties(po)
    return {**invoice_list_row(inv), "rfq_id": po.rfq_id, "rfq_number": po.rfq.rfq_number,
            "payment_terms": po.payment_terms, "buyer": buyer, "vendor": vendor, "items": doc_items(po),
            "totals": doc_totals_out(inv, po.gst_percent), "paid_at": inv.paid_at,
            "created_by_name": inv.creator.name, "created_at": inv.created_at,
            "emails": [{"to_email": e.to_email, "ok": e.ok, "error": e.error, "created_at": e.created_at} for e in inv.emails],
            "email_enabled": bool(settings.smtp_host and settings.smtp_from)}


# ---------------------------------------------------------- access control

def can_see_po(db: Session, user: User, po: PurchaseOrder) -> bool:
    """Staff see every document. A vendor sees only documents issued to its own vendor record."""
    if user.role in STAFF_ROLES:
        return True
    if user.role == Role.vendor:
        return vendor_for_user(db, user).id == po.vendor_id
    return False


def vendor_scope(db: Session, user: User) -> int | None:
    """None means no restriction (staff). For a vendor user, the vendor id to filter by."""
    if user.role in STAFF_ROLES:
        return None
    return vendor_for_user(db, user).id