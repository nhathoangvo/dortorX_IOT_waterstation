# 💧 Doctor.X IoT Platform v2.0

> Smart water intake monitoring system — FastAPI · MQTT · WebSocket · SQLite

---

## Kiến trúc

```
[ESP32 / Simulator] → MQTT → [mqtt_worker.py] → HTTP → [FastAPI Backend]
                                                              ↓
                                                         [SQLite DB]
                                                              ↓
                                              [WebSocket] → [Dashboard Frontend]
```

---

## Cài đặt nhanh (Windows)

### 1. Tạo venv & cài thư viện

```powershell
cd "D:\Final IoT\Final IoT"
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Cấu hình môi trường

```powershell
Copy-Item .env.example .env
# Mở .env, đổi SECRET_KEY thành chuỗi ngẫu nhiên
```

Tạo SECRET_KEY:
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Cấu hình Mosquitto (MQTT auth)

Tạo file mật khẩu MQTT:
```powershell
# Trong thư mục Mosquitto (thường C:\Program Files\Mosquitto)
mosquitto_passwd -c mosquitto_data\passwd iot_worker
# Nhập password khi được hỏi, ghi lại vào .env (MQTT_PASSWORD)
```

Cập nhật `mosquitto.conf` để dùng `password_file`:
```
allow_anonymous false
password_file C:\Path\To\project\mosquitto_data\passwd
```

Khởi động lại Mosquitto:
```powershell
net stop mosquitto
net start mosquitto
```

---

## Chạy hệ thống (3 terminal)

**Terminal 1 — Backend:**
```powershell
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
→ Mở http://localhost:8000

**Terminal 2 — MQTT Worker:**
```powershell
.\venv\Scripts\Activate.ps1
python mqtt_worker.py
```

**Terminal 3 — Device Simulator:**
```powershell
.\venv\Scripts\Activate.ps1
# Trước tiên đăng ký user, thêm device qua dashboard, copy API key
python device_sim.py --device water_station:YOUR_API_KEY --mode http --duration 600
```

---

## Luồng sử dụng

1. Mở http://localhost:8000 → Đăng ký tài khoản
2. Vào Dashboard → Thêm thiết bị → Copy API key
3. Chạy device_sim với API key đó
4. Xem dữ liệu real-time trên Dashboard

---

## Deploy lên Railway (miễn phí)

```bash
# 1. Cài Railway CLI
npm install -g @railway/cli

# 2. Đăng nhập
railway login

# 3. Tạo project
railway init

# 4. Set biến môi trường
railway variables set SECRET_KEY=your_key DATABASE_URL=sqlite:///./iot_platform.db

# 5. Deploy
railway up
```

---

## API Endpoints chính

| Method | Path | Mô tả |
|--------|------|-------|
| POST | /auth/register | Đăng ký |
| POST | /auth/login | Đăng nhập → JWT |
| GET  | /me/profile | Thông tin user |
| GET  | /me/water/dashboard | Full dashboard data |
| GET  | /me/water/summary-today | Tóm tắt hôm nay |
| GET  | /me/water/history?days=7 | Lịch sử 7 ngày |
| POST | /devices | Thêm thiết bị |
| GET  | /devices | Danh sách thiết bị |
| POST | /ingest/telemetry | Nhận dữ liệu từ device |
| WS   | /ws/dashboard?token= | WebSocket real-time |

Swagger UI: http://localhost:8000/docs

---

## Payload format (MQTT / HTTP)

```json
{
  "device_id": "water_station",
  "api_key": "your_api_key_here",
  "metric_type": "water_intake_ml",
  "value": 250,
  "payload": { "volume_ml": 250 }
}
```

MQTT topic: `doctorx/devices/{device_id}/telemetry`

---

## Cấu trúc thư mục

```
doctorx/
├── app/
│   ├── main.py           # FastAPI app
│   ├── db.py             # Database engine
│   ├── models.py         # SQLAlchemy ORM
│   ├── schemas.py        # Pydantic schemas
│   ├── security.py       # JWT, bcrypt, email
│   ├── dependencies.py   # get_current_user
│   ├── ws_manager.py     # WebSocket manager
│   ├── routers/
│   │   ├── auth.py       # /auth/*
│   │   ├── devices.py    # /devices/*
│   │   ├── ingest.py     # /ingest/*
│   │   ├── water.py      # /me/*
│   │   └── ws.py         # /ws/*
│   └── services/
│       └── water.py      # Business logic
├── frontend/
│   ├── index.html        # Login/Register
│   ├── dashboard.html    # Dashboard chính
│   ├── plant.html        # Vườn cây
│   ├── forgot_password.html
│   └── reset_password.html
├── mqtt_worker.py        # MQTT Subscriber
├── device_sim.py         # Device Simulator
├── requirements.txt
├── railway.toml
├── .env.example
└── README.md
```
