from __future__ import annotations
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, LargeBinary
)
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON
from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, default="")
    hashed_password = Column(String, nullable=False)
    gender = Column(String, default="male")       # male | female
    weight_kg = Column(Float, nullable=True)
    height_cm = Column(Float, nullable=True)
    role = Column(String, default="user")         # user | admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    devices = relationship("Device", back_populates="owner", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, default="My Device")
    description = Column(String, default="")
    api_key = Column(String, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    last_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="devices")
    telemetry = relationship("Telemetry", back_populates="device", cascade="all, delete-orphan")


class Telemetry(Base):
    __tablename__ = "telemetry"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, ForeignKey("devices.device_id"), index=True, nullable=False)
    metric_type = Column(String, index=True, nullable=False)
    value = Column(Float, nullable=False)
    payload = Column(JSON, nullable=True)
    ts = Column(DateTime, default=datetime.utcnow, index=True)

    device = relationship("Device", back_populates="telemetry")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="notifications")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)


class FirmwareVersion(Base):
    __tablename__ = "firmware_versions"

    id           = Column(Integer, primary_key=True, index=True)
    version      = Column(String, unique=True, nullable=False)
    download_url = Column(String, nullable=False)
    release_notes = Column(String, default="")
    is_latest    = Column(Boolean, default=False, index=True)
    created_at   = Column(DateTime, default=datetime.utcnow)
    binary_data  = Column(LargeBinary, nullable=True)
