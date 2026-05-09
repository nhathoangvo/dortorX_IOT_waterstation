from __future__ import annotations
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from sqlalchemy import text
from app.db import engine
from app.models import Base
from app.limiter import limiter

# ── import routers ──────────────────────────────────────
from app.routers import auth, devices, ingest, water, ws, admin, notifications, firmware
from app.routers.weather_api import router as weather_router

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self' wss: ws:;"
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        conn.execute(text(
            "ALTER TABLE firmware_versions ADD COLUMN IF NOT EXISTS binary_data BYTEA"
        ))
        conn.commit()
    yield


app = FastAPI(
    title="Doctor.X IoT Platform",
    description="Smart water intake monitoring system",
    version="2.0.0",
    lifespan=lifespan,
)

# ── Rate limiting ────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Security headers ─────────────────────────────────────
app.add_middleware(SecurityHeadersMiddleware)

# ── CORS ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:8000").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# ── API routers ──────────────────────────────────────────
app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(ingest.router)
app.include_router(water.router)
app.include_router(ws.router)
app.include_router(admin.router)
app.include_router(notifications.router)
app.include_router(firmware.router)
app.include_router(weather_router)

# ── Static files ─────────────────────────────────────────
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


def _serve(filename: str) -> FileResponse:
    f = FRONTEND_DIR / filename
    if not f.exists():
        raise HTTPException(404, f"{filename} not found")
    return FileResponse(str(f))


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/app")

@app.get("/app", include_in_schema=False)
def serve_app():
    return _serve("index.html")

@app.get("/dashboard", include_in_schema=False)
def serve_dashboard():
    return _serve("dashboard.html")

@app.get("/garden", include_in_schema=False)
def serve_garden():
    return _serve("plant.html")

@app.get("/forgot-password", include_in_schema=False)
def serve_forgot():
    return _serve("forgot_password.html")

@app.get("/reset-password", include_in_schema=False)
def serve_reset():
    return _serve("reset_password.html")

@app.get("/admin-panel", include_in_schema=False)
def serve_admin_panel():
    return _serve("admin.html")

@app.get("/cam", include_in_schema=False)
def serve_cam():
    return _serve("cam.html")

@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}
