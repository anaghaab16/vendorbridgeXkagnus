import enum
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    Boolean, Date, DateTime, Enum, Float, ForeignKey, ForeignKeyConstraint, Index, Integer, Numeric, String,
    Text, UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def now():
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    procurement_officer = "procurement_officer"
    vendor = "vendor"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))  # "First Last"
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True)  # login username
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.vendor)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(String(60), nullable=True)
    additional_info: Mapped[str | None] = mapped_column(
        String(500), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)


class VendorStatus(str, enum.Enum):
    active = "active"
    pending = "pending"
    blocked = "blocked"


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), index=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gst_number: Mapped[str | None] = mapped_column(String(15), nullable=True)
    contact_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # a vendor user sees RFQs assigned to the vendor whose email matches their login email
    email: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True)
    rating: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[VendorStatus] = mapped_column(
        Enum(VendorStatus), default=VendorStatus.pending)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now)


# ---------------------------------------------------------------- RFQs

class RFQStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    closed = "closed"
    cancelled = "cancelled"


class RFQ(Base):
    __tablename__ = "rfqs"

    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_number: Mapped[str | None] = mapped_column(
        # e.g. RFQ-2026-0001
        String(30), unique=True, index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(220))
    category: Mapped[str] = mapped_column(String(120))
    deadline: Mapped[date] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[RFQStatus] = mapped_column(
        Enum(RFQStatus), default=RFQStatus.draft)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now)

    items: Mapped[list["RFQLineItem"]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan", order_by="RFQLineItem.id")
    vendors: Mapped[list["RFQVendor"]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan")
    attachments: Mapped[list["RFQAttachment"]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan", order_by="RFQAttachment.id")
    quotations: Mapped[list["Quotation"]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan")
    approvals: Mapped[list["ApprovalRequest"]] = relationship(
        viewonly=True, order_by="ApprovalRequest.id")


class RFQLineItem(Base):
    __tablename__ = "rfq_line_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(
        ForeignKey("rfqs.id", ondelete="CASCADE"))
    item_name: Mapped[str] = mapped_column(String(220))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(30))
    rfq: Mapped["RFQ"] = relationship(back_populates="items")


class RFQVendor(Base):
    """Which vendors an RFQ is assigned to."""
    __tablename__ = "rfq_vendors"

    rfq_id: Mapped[int] = mapped_column(ForeignKey(
        "rfqs.id", ondelete="CASCADE"), primary_key=True)
    vendor_id: Mapped[int] = mapped_column(
        ForeignKey("vendors.id"), primary_key=True)
    rfq: Mapped["RFQ"] = relationship(back_populates="vendors")
    vendor: Mapped["Vendor"] = relationship()


class RFQAttachment(Base):
    __tablename__ = "rfq_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(
        ForeignKey("rfqs.id", ondelete="CASCADE"))
    file_name: Mapped[str] = mapped_column(String(240))
    stored_name: Mapped[str] = mapped_column(String(80))
    size: Mapped[int] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now)
    rfq: Mapped["RFQ"] = relationship(back_populates="attachments")


# ----------------------------------------------------------- Quotations

class QuotationStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"


class Quotation(Base):
    __tablename__ = "quotations"
    __table_args__ = (
        # one quotation per vendor per RFQ
        UniqueConstraint("rfq_id", "vendor_id",
                         name="uq_quotation_rfq_vendor"),
        # the database itself refuses a quotation from a vendor that is not assigned to that RFQ
        ForeignKeyConstraint(["rfq_id", "vendor_id"], ["rfq_vendors.rfq_id", "rfq_vendors.vendor_id"],
                             name="fk_quotation_assigned_vendor"),
        # at most one selected quotation per RFQ (this is what Week 3 approvals will read)
        Index("uq_one_selected_quotation", "rfq_id", unique=True,
              postgresql_where=text("is_selected"), sqlite_where=text("is_selected")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(
        ForeignKey("rfqs.id", ondelete="CASCADE"))
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"))
    gst_percent: Mapped[float] = mapped_column(Float, default=0)
    delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(
        String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[QuotationStatus] = mapped_column(
        Enum(QuotationStatus), default=QuotationStatus.draft)
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False)
    selected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now)

    rfq: Mapped["RFQ"] = relationship(back_populates="quotations")
    vendor: Mapped["Vendor"] = relationship()
    items: Mapped[list["QuotationItem"]] = relationship(
        back_populates="quotation", cascade="all, delete-orphan")


class QuotationItem(Base):
    __tablename__ = "quotation_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    quotation_id: Mapped[int] = mapped_column(
        ForeignKey("quotations.id", ondelete="CASCADE"))
    rfq_item_id: Mapped[int] = mapped_column(
        ForeignKey("rfq_line_items.id", ondelete="CASCADE"))
    unit_price: Mapped[float] = mapped_column(Float)
    quotation: Mapped["Quotation"] = relationship(back_populates="items")
    rfq_item: Mapped["RFQLineItem"] = relationship()


# ------------------------------------------------------------ Approvals

class ApprovalStatus(str, enum.Enum):
    awaiting_l1 = "awaiting_l1"
    awaiting_l2 = "awaiting_l2"
    approved = "approved"
    rejected = "rejected"


class StepStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ApprovalRequest(Base):
    """A selected quotation sent for approval. Two levels: L1 review, then L2 approval."""
    __tablename__ = "approval_requests"
    __table_args__ = (
        # an RFQ can have only one live request; a rejected one does not count, so it can be resubmitted
        Index("uq_active_approval_per_rfq", "rfq_id", unique=True,
              postgresql_where=text("status <> 'rejected'"), sqlite_where=text("status <> 'rejected'")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("rfqs.id"))
    quotation_id: Mapped[int] = mapped_column(ForeignKey("quotations.id"))
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus), default=ApprovalStatus.awaiting_l1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    rfq: Mapped["RFQ"] = relationship(viewonly=True)
    quotation: Mapped["Quotation"] = relationship()
    requester: Mapped["User"] = relationship(foreign_keys=[requested_by])
    steps: Mapped[list["ApprovalStep"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="ApprovalStep.level")
    purchase_order: Mapped["PurchaseOrder | None"] = relationship(
        back_populates="approval", uselist=False)


class ApprovalStep(Base):
    __tablename__ = "approval_steps"
    __table_args__ = (UniqueConstraint(
        "request_id", "level", name="uq_step_level"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("approval_requests.id", ondelete="CASCADE"))
    level: Mapped[int] = mapped_column(Integer)  # 1 = review, 2 = approval
    status: Mapped[StepStatus] = mapped_column(
        Enum(StepStatus), default=StepStatus.pending)
    approver_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True)
    remarks: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    acted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    request: Mapped["ApprovalRequest"] = relationship(back_populates="steps")
    approver: Mapped["User | None"] = relationship()


# ------------------------------------------------- Purchase orders, invoices

class POStatus(str, enum.Enum):
    issued = "issued"
    invoiced = "invoiced"
    closed = "closed"


class PurchaseOrder(Base):
    """Created once from an approved quotation. Prices, totals and party details are copied at that moment."""
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    po_number: Mapped[str | None] = mapped_column(
        String(30), unique=True, index=True, nullable=True)
    approval_id: Mapped[int] = mapped_column(ForeignKey(
        "approval_requests.id"), unique=True)  # one PO per approval
    quotation_id: Mapped[int] = mapped_column(
        ForeignKey("quotations.id"), unique=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("rfqs.id"))
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"))
    status: Mapped[POStatus] = mapped_column(
        Enum(POStatus), default=POStatus.issued)
    po_date: Mapped[date] = mapped_column(Date)
    payment_terms: Mapped[str | None] = mapped_column(
        String(120), nullable=True)
    delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gst_percent: Mapped[float] = mapped_column(Float, default=0)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    cgst: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    sgst: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    igst: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    gst_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    grand_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    vendor_name: Mapped[str] = mapped_column(String(150))
    vendor_gst: Mapped[str | None] = mapped_column(String(15), nullable=True)
    vendor_contact: Mapped[str | None] = mapped_column(
        String(20), nullable=True)
    vendor_email: Mapped[str | None] = mapped_column(
        String(255), nullable=True)
    buyer_name: Mapped[str] = mapped_column(String(150))
    buyer_address: Mapped[str | None] = mapped_column(
        String(300), nullable=True)
    buyer_gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now)

    items: Mapped[list["POItem"]] = relationship(
        back_populates="po", cascade="all, delete-orphan", order_by="POItem.id")
    approval: Mapped["ApprovalRequest"] = relationship(
        back_populates="purchase_order")
    quotation: Mapped["Quotation"] = relationship()
    rfq: Mapped["RFQ"] = relationship()
    vendor: Mapped["Vendor"] = relationship()
    creator: Mapped["User"] = relationship()
    invoice: Mapped["Invoice | None"] = relationship(
        back_populates="po", uselist=False)


class POItem(Base):
    __tablename__ = "purchase_order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    po_id: Mapped[int] = mapped_column(ForeignKey(
        "purchase_orders.id", ondelete="CASCADE"))
    item_name: Mapped[str] = mapped_column(String(220))
    unit: Mapped[str] = mapped_column(String(30))
    quantity: Mapped[float] = mapped_column(Float)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    po: Mapped["PurchaseOrder"] = relationship(back_populates="items")


class InvoiceStatus(str, enum.Enum):
    pending_payment = "pending_payment"
    paid = "paid"


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_number: Mapped[str | None] = mapped_column(
        String(30), unique=True, index=True, nullable=True)
    po_id: Mapped[int] = mapped_column(ForeignKey(
        "purchase_orders.id"), unique=True)  # one invoice per PO
    invoice_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus), default=InvoiceStatus.pending_payment)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    cgst: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    sgst: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    igst: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    gst_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    grand_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now)

    po: Mapped["PurchaseOrder"] = relationship(back_populates="invoice")
    creator: Mapped["User"] = relationship()
    emails: Mapped[list["InvoiceEmail"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceEmail.id")


class InvoiceEmail(Base):
    """One row per email attempt, so success and failure are both on record."""
    __tablename__ = "invoice_emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"))
    to_email: Mapped[str] = mapped_column(String(255))
    ok: Mapped[bool] = mapped_column(Boolean)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sent_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now)
    invoice: Mapped["Invoice"] = relationship(back_populates="emails")
