from __future__ import annotations
import os, secrets
from datetime import datetime, timedelta
from typing import Optional
import bcrypt
import resend
from jose import jwt
from sqlalchemy.orm import Session

SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8000")

resend.api_key = RESEND_API_KEY


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    to_encode["jti"] = secrets.token_hex(16)  # unique token ID for audit tracing
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def generate_device_api_key() -> str:
    return secrets.token_hex(32)  # 64 hex chars = 256-bit entropy


def create_password_reset_token(db: Session, user_id: int) -> str:
    from app.models import PasswordResetToken
    # Invalidate all prior unused tokens for this user
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user_id,
        PasswordResetToken.used == False,
    ).update({"used": True})
    token = secrets.token_urlsafe(32)
    expire = datetime.utcnow() + timedelta(minutes=30)
    db.add(PasswordResetToken(user_id=user_id, token=token, expires_at=expire))
    db.commit()
    return token


def verify_password_reset_token(db: Session, token: str) -> Optional[int]:
    from app.models import PasswordResetToken
    record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token,
        PasswordResetToken.used == False,
        PasswordResetToken.expires_at > datetime.utcnow(),
    ).first()
    if not record:
        return None
    record.used = True
    db.commit()
    return record.user_id


def get_user_by_email(db: Session, email: str):
    from app.models import User
    return db.query(User).filter(User.email == email).first()


def authenticate_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


def send_password_reset_email(email: str, token: str) -> None:
    reset_link = f"{FRONTEND_URL}/reset-password?token={token}"
    if not RESEND_API_KEY:
        print(f"[DEV] Reset link: {reset_link}")
        return
    resend.Emails.send({
        "from": "Doctor.X <onboarding@resend.dev>",
        "to": [email],
        "subject": "Doctor.X — Đặt lại mật khẩu",
        "text": f"Link đặt lại mật khẩu (hết hạn 30 phút):\n\n{reset_link}",
    })
