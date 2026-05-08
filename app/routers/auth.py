from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db import get_db
from app.limiter import limiter
from app.models import User
from app.schemas import UserCreate, UserOut, Token, ForgotPasswordRequest, ResetPasswordRequest
from app.security import (
    get_password_hash, create_access_token, create_password_reset_token,
    verify_password_reset_token, send_password_reset_email,
    get_user_by_email, authenticate_user,
)

logger = logging.getLogger("security")
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
@limiter.limit("3/minute")
async def register(request: Request, body: UserCreate, db: Session = Depends(get_db)):
    if get_user_by_email(db, body.email):
        raise HTTPException(400, "Email đã được đăng ký")
    user = User(
        email=body.email,
        full_name=body.full_name,
        hashed_password=get_password_hash(body.password),
        gender=body.gender,
        weight_kg=body.weight_kg,
        height_cm=body.height_cm,
    )
    db.add(user); db.commit(); db.refresh(user)
    logger.info("REGISTER user_id=%s ip=%s", user.id, request.client.host)
    return user


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
async def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form.username, form.password)
    if not user:
        logger.warning("LOGIN_FAILED email=%s ip=%s", form.username, request.client.host)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sai email hoặc mật khẩu")
    logger.info("LOGIN_SUCCESS user_id=%s ip=%s", user.id, request.client.host)
    return {"access_token": create_access_token({"sub": str(user.id)}), "token_type": "bearer"}


@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(request: Request, body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = get_user_by_email(db, body.email)
    if user:
        token = create_password_reset_token(db, user.id)
        try:
            send_password_reset_email(user.email, token)
        except Exception as e:
            logger.error("EMAIL_SEND_FAILED email=%s err=%s", body.email, e)
    return {"message": "Nếu email tồn tại, link đặt lại mật khẩu đã được gửi."}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    user_id = verify_password_reset_token(db, body.token)
    if not user_id:
        raise HTTPException(400, "Token không hợp lệ hoặc đã hết hạn")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(400, "User không tồn tại")
    user.hashed_password = get_password_hash(body.new_password)
    db.commit()
    logger.info("PASSWORD_RESET user_id=%s", user_id)
    return {"message": "Mật khẩu đã được thay đổi thành công"}
