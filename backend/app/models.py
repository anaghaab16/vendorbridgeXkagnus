import enum
from datetime import date, datetime, timezone
from sqlalchemy import (
    Boolean, Date, DateTime, Enum, Float, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text,
    UniqueConstraint, text,
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
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)  # login username
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.vendor)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(String(60), nullable=True)
    additional_info: Mapped[str | None] = mapped_column(String(500), nullable=True)
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
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    rating: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[VendorStatus] = mapped_column(Enum(VendorStatus), default=VendorStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------- RFQs

class RFQStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    closed = "closed"
    cancelled = "cancelled"


class RFQ(Base):
    __tablename__ = "rfqs"

    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_number: Mapped[str | None] = mapped_column(String(30), unique=True, index=True, nullable=True)  # e.g. RFQ-2026-0001
    title: Mapped[str] = mapped_column(String(220))
    category: Mapped[str] = mapped_column(String(120))
    deadline: Mapped[date] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[RFQStatus] = mapped_column(Enum(RFQStatus), default=RFQStatus.draft)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    items: Mapped[list["RFQLineItem"]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan", order_by="RFQLineItem.id")
    vendors: Mapped[list["RFQVendor"]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan")
    attachments: Mapped[list["RFQAttachment"]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan", order_by="RFQAttachment.id")
    quotations: Mapped[list["Quotation"]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan")


class RFQLineItem(Base):
    __tablename__ = "rfq_line_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("rfqs.id", ondelete="CASCADE"))
    item_name: Mapped[str] = mapped_column(String(220))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(30))
    rfq: Mapped["RFQ"] = relationship(back_populates="items")


class RFQVendor(Base):
    """Which vendors an RFQ is assigned to."""
    __tablename__ = "rfq_vendors"

    rfq_id: Mapped[int] = mapped_column(ForeignKey("rfqs.id", ondelete="CASCADE"), primary_key=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), primary_key=True)
    rfq: Mapped["RFQ"] = relationship(back_populates="vendors")
    vendor: Mapped["Vendor"] = relationship()


class RFQAttachment(Base):
    __tablename__ = "rfq_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("rfqs.id", ondelete="CASCADE"))
    file_name: Mapped[str] = mapped_column(String(240))
    stored_name: Mapped[str] = mapped_column(String(80))
    size: Mapped[int] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    rfq: Mapped["RFQ"] = relationship(back_populates="attachments")


# ----------------------------------------------------------- Quotations

class QuotationStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"


class Quotation(Base):
    __tablename__ = "quotations"
    __table_args__ = (
        # one quotation per vendor per RFQ
        UniqueConstraint("rfq_id", "vendor_id", name="uq_quotation_rfq_vendor"),
        # the database itself refuses a quotation from a vendor that is not assigned to that RFQ
        ForeignKeyConstraint(["rfq_id", "vendor_id"], ["rfq_vendors.rfq_id", "rfq_vendors.vendor_id"],
                             name="fk_quotation_assigned_vendor"),
        # at most one selected quotation per RFQ (this is what Week 3 approvals will read)
        Index("uq_one_selected_quotation", "rfq_id", unique=True,
              postgresql_where=text("is_selected"), sqlite_where=text("is_selected")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("rfqs.id", ondelete="CASCADE"))
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"))
    gst_percent: Mapped[float] = mapped_column(Float, default=0)
    delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[QuotationStatus] = mapped_column(Enum(QuotationStatus), default=QuotationStatus.draft)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False)
    selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    rfq: Mapped["RFQ"] = relationship(back_populates="quotations")
    vendor: Mapped["Vendor"] = relationship()
    items: Mapped[list["QuotationItem"]] = relationship(
        back_populates="quotation", cascade="all, delete-orphan")


class QuotationItem(Base):
    __tablename__ = "quotation_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    quotation_id: Mapped[int] = mapped_column(ForeignKey("quotations.id", ondelete="CASCADE"))
    rfq_item_id: Mapped[int] = mapped_column(ForeignKey("rfq_line_items.id", ondelete="CASCADE"))
    unit_price: Mapped[float] = mapped_column(Float)
    quotation: Mapped["Quotation"] = relationship(back_populates="items")
    rfq_item: Mapped["RFQLineItem"] = relationship()