from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Any, Dict, Literal
from pydantic import BaseModel, EmailStr, field_validator, Field


def _check_password_strength(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Mật khẩu tối thiểu 8 ký tự")
    if not any(c.isupper() for c in v):
        raise ValueError("Mật khẩu phải có ít nhất 1 chữ hoa")
    if not any(c.isdigit() for c in v):
        raise ValueError("Mật khẩu phải có ít nhất 1 chữ số")
    return v


# ─── AUTH ────────────────────────────────────────────────
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str = Field(default="", max_length=100)
    gender: str = "male"
    weight_kg: Optional[float] = Field(default=None, ge=1, le=500)
    height_cm: Optional[float] = Field(default=None, ge=50, le=300)

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: str) -> str:
        if v not in ("male", "female"):
            raise ValueError("gender must be 'male' or 'female'")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _check_password_strength(v)


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=100)
    gender: Optional[str] = None
    weight_kg: Optional[float] = Field(default=None, ge=1, le=500)
    height_cm: Optional[float] = Field(default=None, ge=50, le=300)


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    gender: str
    weight_kg: Optional[float]
    height_cm: Optional[float]
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return _check_password_strength(v)


# ─── DEVICE ──────────────────────────────────────────────
class DeviceCreate(BaseModel):
    device_id: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9_\-]+$')
    name: str = Field(default="My Device", max_length=100)
    description: str = Field(default="", max_length=500)


class DeviceOut(BaseModel):
    id: int
    device_id: str
    name: str
    description: str
    api_key: str
    is_active: bool
    last_seen: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── TELEMETRY ───────────────────────────────────────────
class TelemetryIn(BaseModel):
    device_id: str = Field(max_length=64)
    api_key: str = Field(max_length=64)
    metric_type: Literal["water_intake_ml"]
    value: float = Field(ge=0, le=10000)
    payload: Optional[Dict[str, Any]] = None


class TelemetryOut(BaseModel):
    id: int
    device_id: str
    metric_type: str
    value: float
    payload: Optional[Dict[str, Any]]
    ts: datetime

    model_config = {"from_attributes": True}


# ─── WATER / DASHBOARD ───────────────────────────────────
class WaterSummaryOut(BaseModel):
    date: str
    total_ml: float
    target_ml: float
    percent: float
    plant_state: str        # dry | growing | healthy | bloom
    time_slot: str          # morning | lunch | afternoon | night
    image: str
    streak_days: int = 0
    glasses: int = 0        # số ly quy đổi (250ml/ly)


class WaterHistoryDay(BaseModel):
    date: str
    total_ml: float
    percent: float
    achieved: bool = False


class WaterHistoryOut(BaseModel):
    days: List[WaterHistoryDay]


class HourlyPoint(BaseModel):
    hour: int
    total_ml: float


class DashboardOut(BaseModel):
    today: WaterSummaryOut
    last_7_days: List[WaterHistoryDay]
    hourly_today: List[HourlyPoint]
    devices: List[DeviceOut]


# ─── ADMIN ───────────────────────────────────────────────
class RoleUpdate(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("user", "admin"):
            raise ValueError("role must be 'user' or 'admin'")
        return v


# ─── NOTIFICATION ────────────────────────────────────────
class NotificationOut(BaseModel):
    id: int
    message: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
