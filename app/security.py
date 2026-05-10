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


_SLOT_MESSAGES = {
    "morning":   ("☀️ Bắt đầu ngày mới!", "Đừng quên uống nước ngay sau khi thức dậy để khởi động cơ thể nhé!"),
    "lunch":     ("🍱 Giờ ăn trưa rồi!", "Uống một ly nước trước bữa ăn giúp tiêu hoá tốt hơn đó!"),
    "afternoon": ("☕ Buổi chiều uể oải?", "Uống thêm nước để duy trì năng lượng — đừng để cơ thể mất nước nhé!"),
    "evening":   ("🌙 Sắp hết ngày rồi!", "Cố thêm một chút nữa để hoàn thành mục tiêu hôm nay nhé!"),
}


def send_reminder_email(email: str, name: str, total_ml: float, target_ml: float, percent: float, slot: str) -> None:
    if not RESEND_API_KEY:
        print(f"[DEV] Reminder → {email} | {total_ml:.0f}/{target_ml:.0f}ml ({percent:.0f}%)")
        return
    title, message = _SLOT_MESSAGES.get(slot, ("💧 Nhắc uống nước", "Hãy uống thêm nước nhé!"))
    remaining = max(0, target_ml - total_ml)
    bar_width = min(int(percent), 100)
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f0f9ff;font-family:Arial,sans-serif;">
  <div style="max-width:520px;margin:30px auto;background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08);">
    <div style="background:linear-gradient(135deg,#00d2c8,#00aaff);padding:30px 30px 20px;text-align:center;">
      <div style="font-size:2.5rem;">💧</div>
      <h1 style="margin:8px 0 0;color:#fff;font-size:1.3rem;font-weight:700;">Doctor.X</h1>
      <p style="margin:4px 0 0;color:rgba(255,255,255,0.85);font-size:.9rem;">Smart Water Tracker</p>
    </div>
    <div style="padding:28px 30px;">
      <h2 style="margin:0 0 6px;color:#1a2a3a;font-size:1.1rem;">{title}</h2>
      <p style="margin:0 0 20px;color:#555;font-size:.95rem;">Xin chào <strong>{name}</strong>! {message}</p>
      <div style="background:#f8fbff;border-radius:12px;padding:20px;margin-bottom:20px;">
        <div style="display:flex;justify-content:space-between;margin-bottom:10px;">
          <span style="color:#666;font-size:.85rem;">Đã uống hôm nay</span>
          <span style="color:#00aaff;font-weight:700;font-size:.95rem;">{total_ml:.0f} / {target_ml:.0f} ml</span>
        </div>
        <div style="background:#e0edf5;border-radius:6px;height:14px;overflow:hidden;">
          <div style="background:linear-gradient(90deg,#00d2c8,#00aaff);width:{bar_width}%;height:14px;border-radius:6px;"></div>
        </div>
        <div style="text-align:center;margin-top:8px;font-size:.8rem;color:#888;">{percent:.0f}% mục tiêu ngày</div>
      </div>
      <p style="margin:0 0 20px;color:#555;font-size:.9rem;">
        Bạn còn cần uống thêm <strong style="color:#00aaff;">{remaining:.0f} ml</strong> nữa để đạt mục tiêu hôm nay!
      </p>
      <div style="text-align:center;">
        <a href="{FRONTEND_URL}/dashboard"
           style="display:inline-block;background:linear-gradient(90deg,#00d2c8,#00aaff);color:#fff;padding:12px 32px;border-radius:30px;text-decoration:none;font-weight:700;font-size:.95rem;box-shadow:0 4px 12px rgba(0,210,200,0.35);">
          Xem Dashboard →
        </a>
      </div>
    </div>
    <div style="padding:16px 30px;border-top:1px solid #eef2f7;text-align:center;">
      <p style="margin:0;color:#aaa;font-size:.75rem;">Doctor.X IoT Platform · Bạn nhận email này vì đã đăng ký tài khoản.</p>
    </div>
  </div>
</body>
</html>"""
    resend.Emails.send({
        "from": "Doctor.X <onboarding@resend.dev>",
        "to": [email],
        "subject": f"Doctor.X — {title} ({percent:.0f}% mục tiêu)",
        "html": html,
    })
