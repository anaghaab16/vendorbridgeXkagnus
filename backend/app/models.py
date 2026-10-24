import enum
from datetime import datetime, timezone
from sqlalchemy import String, Enum, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Role(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    procurement_officer = "procurement_officer"
    vendor = "vendor"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))  # "First Last"
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)  # used as the login username
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.vendor)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
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
    status: Mapped[VendorStatus] = mapped_column(Enum(VendorStatus), default=VendorStatus.pending)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )