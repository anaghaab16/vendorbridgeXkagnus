import re
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.models import QuotationStatus, RFQStatus, Role, VendorStatus

PHONE_RE = r"\+?[0-9 \-]{10,16}"
GST_RE = r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]"


def _blank_to_none(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


# ------------------------------------------------------------------ users

class RegisterIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    email: EmailStr
    phone: str = Field(pattern=f"^{PHONE_RE}$")
    role: Role = Role.procurement_officer
    country: str = Field(min_length=2, max_length=60)
    additional_info: str | None = Field(default=None, max_length=500)
    password: str = Field(min_length=8)

    @field_validator("additional_info", mode="before")
    @classmethod
    def blank_info(cls, v):
        return _blank_to_none(v)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, v: str) -> str:
        if len(v.encode()) > 72:  # bcrypt rejects longer passwords
            raise ValueError("Password must be 72 bytes or fewer")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: EmailStr
    phone: str | None
    country: str | None
    additional_info: str | None
    photo_url: str | None
    role: Role
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------- vendors

class VendorIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    category: str | None = Field(default=None, max_length=100)
    gst_number: str | None = None
    contact_no: str | None = None
    email: EmailStr | None = None
    rating: float = Field(default=0, ge=0, le=5)
    status: VendorStatus = VendorStatus.pending

    @field_validator("category", "gst_number", "contact_no", "email", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return _blank_to_none(v)

    @field_validator("email")
    @classmethod
    def lower_email(cls, v):
        return v.lower() if v else v

    @field_validator("gst_number")
    @classmethod
    def gst_format(cls, v):
        if v is None:
            return v
        v = v.upper()
        if not re.fullmatch(GST_RE, v):
            raise ValueError("GST number must be 15 characters, like 27AABCS1429B1Z5")
        return v

    @field_validator("contact_no")
    @classmethod
    def contact_format(cls, v):
        if v is not None and not re.fullmatch(PHONE_RE, v):
            raise ValueError("Contact number must be 10 to 15 digits")
        return v


class VendorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    category: str | None
    gst_number: str | None
    contact_no: str | None
    email: str | None
    rating: float
    status: VendorStatus
    created_at: datetime


# ------------------------------------------------------------------- RFQs

class RFQItemIn(BaseModel):
    item_name: str = Field(min_length=1, max_length=220)
    quantity: float = Field(gt=0, le=10_000_000)
    unit: str = Field(min_length=1, max_length=30)


class RFQIn(BaseModel):
    title: str = Field(min_length=3, max_length=220)
    category: str = Field(min_length=2, max_length=120)
    deadline: date
    description: str | None = Field(default=None, max_length=2000)
    items: list[RFQItemIn] = Field(min_length=1, max_length=50)
    vendor_ids: list[int] = Field(default_factory=list, max_length=50)
    send: bool = False

    @field_validator("description", mode="before")
    @classmethod
    def blank_description(cls, v):
        return _blank_to_none(v)

    @field_validator("vendor_ids")
    @classmethod
    def unique_vendor_ids(cls, v):
        return list(dict.fromkeys(v))


class RFQStatusIn(BaseModel):
    status: RFQStatus


class RFQItemOut(BaseModel):
    id: int
    item_name: str
    quantity: float
    unit: str


class AttachmentOut(BaseModel):
    id: int
    file_name: str
    size: int
    uploaded_at: datetime


class RFQListOut(BaseModel):
    id: int
    rfq_number: str | None
    title: str
    category: str
    deadline: date
    status: RFQStatus
    created_at: datetime
    item_count: int
    vendor_count: int
    quote_count: int
    deadline_passed: bool
    selected_vendor_name: str | None


class RFQVendorOut(BaseModel):
    vendor_id: int
    name: str
    rating: float
    email: str | None
    quotation_status: QuotationStatus | None


class RFQDetailOut(RFQListOut):
    selected_quotation_id: int | None
    description: str | None
    items: list[RFQItemOut]
    vendors: list[RFQVendorOut]
    attachments: list[AttachmentOut]


# ------------------------------------------------------------- quotations

class QuoteItemIn(BaseModel):
    rfq_item_id: int
    unit_price: float = Field(ge=0, le=1_000_000_000)


class QuotationIn(BaseModel):
    items: list[QuoteItemIn] = Field(default_factory=list, max_length=50)
    gst_percent: float = Field(default=0, ge=0, le=100)
    delivery_days: int | None = Field(default=None, ge=1, le=730)
    payment_terms: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=1000)
    submit: bool = False

    @field_validator("payment_terms", "notes", mode="before")
    @classmethod
    def blank_text(cls, v):
        return _blank_to_none(v)


class QuoteLineOut(BaseModel):
    rfq_item_id: int
    item_name: str
    quantity: float
    unit: str
    unit_price: float | None
    line_total: float | None


class QuotationOut(BaseModel):
    id: int
    status: QuotationStatus
    gst_percent: float
    delivery_days: int | None
    payment_terms: str | None
    notes: str | None
    submitted_at: datetime | None
    updated_at: datetime
    lines: list[QuoteLineOut]
    subtotal: float
    gst_amount: float
    total: float


class MyRFQListOut(BaseModel):
    id: int
    rfq_number: str | None
    title: str
    category: str
    deadline: date
    status: RFQStatus
    deadline_passed: bool
    my_quotation_status: QuotationStatus | None


class MyRFQDetailOut(BaseModel):
    id: int
    rfq_number: str | None
    title: str
    category: str
    deadline: date
    description: str | None
    status: RFQStatus
    deadline_passed: bool
    can_edit: bool
    vendor_name: str
    items: list[RFQItemOut]
    attachments: list[AttachmentOut]
    quotation: QuotationOut | None


class CompareColumn(BaseModel):
    quotation_id: int
    vendor_id: int
    vendor_name: str
    rating: float
    gst_percent: float
    delivery_days: int | None
    payment_terms: str | None
    notes: str | None
    submitted_at: datetime | None
    lines: list[QuoteLineOut]
    subtotal: float
    gst_amount: float
    total: float
    is_lowest: bool
    is_fastest: bool
    is_selected: bool


class CompareOut(BaseModel):
    rfq_id: int
    rfq_number: str | None
    selected_quotation_id: int | None
    title: str
    deadline: date
    status: RFQStatus
    items: list[RFQItemOut]
    quotes: list[CompareColumn]
    waiting: list[str]


class SelectIn(BaseModel):
    quotation_id: int | None = None  # None clears the selection