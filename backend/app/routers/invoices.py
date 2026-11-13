from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit, mailer
from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import Invoice, InvoiceEmail, PurchaseOrder, Role, User
from app.pdf import inr, invoice_pdf
from app.schemas import (
    EmailIn, EmailResultOut, InvoiceCreateIn, InvoiceDetailOut, InvoiceListOut,
)
from app.workflow import (
    STAFF_ROLES, can_see_po, generate_invoice, invoice_detail, invoice_list_row, mark_paid, vendor_scope,
)

router = APIRouter(prefix="/invoices", tags=["invoices"])
OFFICERS = (Role.admin, Role.procurement_officer)
FINANCE = (Role.admin, Role.manager)


def load(db: Session, user: User, invoice_id: int) -> Invoice:
    inv = db.get(Invoice, invoice_id)
    if inv is None or not can_see_po(db, user, inv.po):  # same rule as the PO: staff, or the vendor it was issued to
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invoice not found")
    return inv


@router.get("", response_model=list[InvoiceListOut])
def list_invoices(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = select(Invoice).order_by(Invoice.created_at.desc())
    vendor_id = vendor_scope(db, user)
    if vendor_id is not None:
        query = query.join(PurchaseOrder, PurchaseOrder.id == Invoice.po_id).where(PurchaseOrder.vendor_id == vendor_id)
    return [invoice_list_row(i) for i in db.scalars(query).all()]


@router.post("", response_model=InvoiceDetailOut, status_code=status.HTTP_201_CREATED)
def create_invoice(data: InvoiceCreateIn, db: Session = Depends(get_db),
                   user: User = Depends(require_roles(*OFFICERS))):
    return invoice_detail(generate_invoice(db, data.po_id, user))


@router.get("/{invoice_id}", response_model=InvoiceDetailOut)
def read_invoice(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return invoice_detail(load(db, user, invoice_id))


@router.get("/{invoice_id}/pdf")
def download_pdf(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    inv = load(db, user, invoice_id)
    pdf = invoice_pdf(invoice_detail(inv))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{inv.invoice_number}.pdf"'})


@router.patch("/{invoice_id}/mark-paid", response_model=InvoiceDetailOut)
def pay(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*FINANCE))):
    return invoice_detail(mark_paid(db, load(db, user, invoice_id), user))


@router.post("/{invoice_id}/email", response_model=EmailResultOut)
def email_invoice(invoice_id: int, data: EmailIn, db: Session = Depends(get_db),
                  user: User = Depends(require_roles(*STAFF_ROLES))):
    inv = load(db, user, invoice_id)
    to = data.to or inv.po.vendor_email
    if not to:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "This vendor has no email. Enter an address to send to.")
    if not mailer.email_enabled():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Email is not configured on the server. Set the SMTP settings in .env and restart.")
    detail = invoice_detail(inv)
    try:
        mailer.send_invoice_email(to, inv.invoice_number, inv.po.vendor_name, f"INR {inr(inv.grand_total)}",
                                  inv.due_date.strftime("%d %b %Y"), invoice_pdf(detail))
    except mailer.MailFailed as exc:
        db.add(InvoiceEmail(invoice_id=inv.id, to_email=to, ok=False, error=str(exc)[:300], sent_by=user.id))
        audit.record(db, user, "invoice.email_failed", "invoice", inv.id, inv.invoice_number,
                     f"{user.name} tried to email {inv.invoice_number} to {to}, but it failed")
        db.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The email server refused or did not answer. Check the SMTP settings and try again.")
    db.add(InvoiceEmail(invoice_id=inv.id, to_email=to, ok=True, sent_by=user.id))
    audit.record(db, user, "invoice.emailed", "invoice", inv.id, inv.invoice_number,
                 f"{user.name} emailed {inv.invoice_number} to {to}")
    db.commit()
    return {"ok": True, "to": to, "message": f"Invoice {inv.invoice_number} sent to {to}"}