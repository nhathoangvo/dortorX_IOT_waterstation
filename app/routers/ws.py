from __future__ import annotations
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt
from app.security import SECRET_KEY, ALGORITHM
from app.db import SessionLocal
from app.models import User
from app.ws_manager import manager
from app.services import water as svc

router = APIRouter(tags=["websocket"])


async def get_user_from_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        return None
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()


@router.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket, token: str = Query(...)):
    user = await get_user_from_token(token)
    if not user:
        await websocket.close(code=4001)
        return

    await manager.connect(websocket, user.id)
    try:
        db = SessionLocal()
        try:
            summary = svc.get_today_summary(db, user)
            await websocket.send_json({"type": "init", "data": summary.model_dump()})
        finally:
            db.close()

        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if msg == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                await websocket.send_text("ping")
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, user.id)


_cam_source: WebSocket | None = None
_cam_viewers: set = set()


@router.websocket("/ws/cam")
async def ws_cam(websocket: WebSocket, token: str = Query(...)):
    user = await get_user_from_token(token)
    if not user:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    global _cam_source, _cam_viewers
    role = None
    try:
        msg = await websocket.receive()
        if msg["type"] == "websocket.disconnect":
            return
        role_msg = msg.get("text", "")

        if role_msg == "source":
            _cam_source = websocket
            role = "source"
            while True:
                msg = await websocket.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                if msg.get("bytes"):
                    dead = set()
                    for viewer in list(_cam_viewers):
                        try:
                            await viewer.send_bytes(msg["bytes"])
                        except Exception:
                            dead.add(viewer)
                    _cam_viewers -= dead
        elif role_msg == "viewer":
            _cam_viewers.add(websocket)
            role = "viewer"
            while True:
                await asyncio.sleep(1)
                try:
                    await websocket.send_text(".")
                except Exception:
                    break
    except asyncio.TimeoutError:
        pass
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if role == "source" and _cam_source == websocket:
            _cam_source = None
        elif role == "viewer":
            _cam_viewers.discard(websocket)
