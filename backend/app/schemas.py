import re
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.models import Role, VendorStatus

PHONE_RE = r"\+?[0-9 \-]{10,16}"
GST_RE = r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]"


def _blank_to_none(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


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


class VendorIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    category: str | None = Field(default=None, max_length=100)
    gst_number: str | None = None
    contact_no: str | None = None
    status: VendorStatus = VendorStatus.pending

    @field_validator("category", "gst_number", "contact_no", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return _blank_to_none(v)

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
    status: VendorStatus
    created_at: datetime