from fastapi import FastAPI, APIRouter, HTTPException, Query, BackgroundTasks, Header, Request, Depends, Response
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import hmac
import logging
import asyncio
import jwt
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import sheets_service
from sheets_service import SheetsError

# MongoDB connection (kept from foundation; used for app-level metadata later)
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

WEBHOOK_CRON_SECRET = os.environ.get("WEBHOOK_CRON_SECRET")
LOCAL_TZ = ZoneInfo(os.environ.get("APP_TIMEZONE", "Asia/Jakarta"))


def today_local() -> str:
    """Today's date (YYYY-MM-DD) in the app's local timezone."""
    return datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Authentication (stateless JWT) + simple in-memory login rate limiting
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_ALG = "HS256"
TOKEN_TTL_HOURS = 12

LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW = timedelta(minutes=15)
_login_fails: dict = {}


def _prune_fails(key: str):
    now = datetime.now(timezone.utc)
    _login_fails[key] = [t for t in _login_fails.get(key, []) if now - t < LOGIN_WINDOW]


def _is_locked(key: str) -> bool:
    _prune_fails(key)
    return len(_login_fails.get(key, [])) >= LOGIN_MAX_ATTEMPTS


def _record_fail(key: str):
    _prune_fails(key)
    _login_fails.setdefault(key, []).append(datetime.now(timezone.utc))


def _clear_fails(key: str):
    _login_fails.pop(key, None)


def create_access_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


async def get_current_user(request: Request) -> dict:
    """Auth dependency: reads JWT from httpOnly cookie (fallback Bearer header)."""
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Belum login")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Token tidak valid")
        return {"username": payload["sub"], "role": payload.get("role", "")}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesi berakhir, silakan login lagi")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token tidak valid")

app = FastAPI(title="Sistem Absensi Sekolah API")
api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"message": "Sistem Absensi Sekolah API", "status": "ok"}


@api_router.get("/config/sheets")
async def sheets_config():
    """Expose Google Sheets configuration status + the service account email.

    Handy for onboarding: the frontend can show which email to share the sheet with.
    """
    return sheets_service.get_config_status()


class LoginRequest(BaseModel):
    username: str
    password: str


@api_router.post("/login")
async def login(payload: LoginRequest, request: Request, response: Response):
    """Verify username/password against the 'Users' sheet (hash compare) and issue a JWT."""
    username = payload.username.strip()
    xff = request.headers.get("x-forwarded-for", "")
    ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown")
    key = f"{ip}:{username.lower()}"

    if _is_locked(key):
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak percobaan login. Coba lagi dalam beberapa menit.",
        )

    try:
        users = await asyncio.to_thread(sheets_service.read_users)
    except SheetsError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message})

    user = next((u for u in users if u.get("Username", "").strip() == username), None)
    if not user or not sheets_service.verify_password(payload.password, user.get("Password_Hash", "")):
        _record_fail(key)
        # Generic message on purpose — do not reveal which field was wrong.
        raise HTTPException(status_code=401, detail="Username atau password salah")

    _clear_fails(key)

    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        await asyncio.to_thread(
            sheets_service.write_user,
            user.get("Nama", ""),
            username,
            user.get("Password_Hash", ""),
            user.get("Role", "") or "guru",
            now_iso,
            user.get("ID_User") or None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gagal update Terakhir_Login: %s", exc)
    try:
        await asyncio.to_thread(
            sheets_service.append_log, username, "Login", f"User {username} berhasil login"
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gagal menulis log Login: %s", exc)

    token = create_access_token(username, user.get("Role", ""))
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=TOKEN_TTL_HOURS * 3600,
        path="/",
    )
    # Never return Password_Hash.
    return {
        "user": {"username": username, "nama": user.get("Nama", ""), "role": user.get("Role", "")},
        "token": token,
    }


@api_router.get("/me")
async def me(current: dict = Depends(get_current_user)):
    return {"user": current}


@api_router.post("/logout")
async def logout(response: Response, current: dict = Depends(get_current_user)):
    try:
        await asyncio.to_thread(
            sheets_service.append_log, current["username"], "Logout", f"User {current['username']} logout"
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gagal menulis log Logout: %s", exc)
    response.delete_cookie(key="access_token", path="/")
    return {"ok": True}


@api_router.get("/siswa")
async def get_siswa(current: dict = Depends(get_current_user)):
    """Return all rows from the 'Master_Siswa' sheet."""
    try:
        data = await asyncio.to_thread(sheets_service.read_master_siswa)
        return {"data": data, "count": len(data)}
    except SheetsError as exc:
        logger.error("Gagal membaca Master_Siswa: %s", exc.message)
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message})


@api_router.get("/absensi")
async def get_absensi(
    tanggal: Optional[str] = Query(None, description="Filter tanggal YYYY-MM-DD"),
    current: dict = Depends(get_current_user),
):
    """Return rows from the 'Absensi' sheet, optionally filtered by tanggal."""
    try:
        data = await asyncio.to_thread(sheets_service.read_absensi, tanggal)
        return {"data": data, "count": len(data), "tanggal": tanggal}
    except SheetsError as exc:
        logger.error("Gagal membaca Absensi: %s", exc.message)
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message})


ALLOWED_STATUS = {"Hadir", "Sakit", "Ijin", "Pulang"}


class AbsensiUpdate(BaseModel):
    id_siswa: str
    tanggal: str
    nama: str = ""
    kelas: str = ""
    status: str = "Hadir"
    keterangan: str = ""


@api_router.post("/absensi")
async def upsert_absensi(payload: AbsensiUpdate, current: dict = Depends(get_current_user)):
    """Insert or update one row in 'Absensi' (no duplicate per ID_Siswa + Tanggal)."""
    if payload.status not in ALLOWED_STATUS:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_status",
                "message": f"Status harus salah satu dari: {', '.join(sorted(ALLOWED_STATUS))}.",
            },
        )
    if not payload.id_siswa.strip() or not payload.tanggal.strip():
        raise HTTPException(
            status_code=422,
            detail={"code": "missing_field", "message": "id_siswa dan tanggal wajib diisi."},
        )
    try:
        result = await asyncio.to_thread(
            sheets_service.write_absensi_row,
            payload.id_siswa,
            payload.tanggal,
            payload.nama,
            payload.kelas,
            payload.status,
            payload.keterangan,
        )
        try:
            await asyncio.to_thread(
                sheets_service.append_log,
                "guru",
                "Ubah Status Absensi",
                f"{payload.nama or payload.id_siswa} → {payload.status}",
            )
        except Exception as log_exc:  # noqa: BLE001
            logger.warning("Gagal menulis Log_Aktivitas: %s", log_exc)
        return {"ok": True, "action": result["action"], "row": result["row"]}
    except SheetsError as exc:
        logger.error("Gagal menulis Absensi: %s", exc.message)
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message})


class GenerateRequest(BaseModel):
    tanggal: Optional[str] = None


@api_router.post("/generate-absensi")
async def generate_absensi(
    payload: GenerateRequest = GenerateRequest(),
    current: dict = Depends(get_current_user),
):
    """Manual trigger: append default 'Hadir' rows for students missing them today.

    Used for testing the daily job without waiting for the schedule.
    """
    tanggal = (payload.tanggal or today_local()).strip()
    try:
        result = await asyncio.to_thread(sheets_service.generate_absensi_for_date, tanggal)
        return {"ok": True, **result}
    except SheetsError as exc:
        logger.error("Gagal generate absensi: %s", exc.message)
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message})


def _run_generate_bg(tanggal: str):
    try:
        result = sheets_service.generate_absensi_for_date(tanggal)
        logger.info("Cron generate-absensi %s: %s", tanggal, result)
    except Exception as exc:  # noqa: BLE001
        logger.error("Cron generate-absensi gagal untuk %s: %s", tanggal, exc)


@api_router.post("/cron/generate-absensi")
async def cron_generate_absensi(
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None),
):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    if not WEBHOOK_CRON_SECRET:
        raise HTTPException(status_code=500, detail="WEBHOOK_CRON_SECRET belum dikonfigurasi.")
    expected = f"Bearer {WEBHOOK_CRON_SECRET}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")

    tanggal = today_local()
    background_tasks.add_task(_run_generate_bg, tanggal)
    return {"ok": True, "accepted": True, "tanggal": tanggal}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def on_startup():
    """Ensure new sheet structure exists and seed the default admin (idempotent)."""
    try:
        await asyncio.to_thread(sheets_service.ensure_structure)
        await asyncio.to_thread(
            sheets_service.seed_default_admin,
            os.environ.get("ADMIN_USERNAME", "admin"),
            os.environ.get("ADMIN_PASSWORD", "admin123"),
        )
        logger.info("Struktur sheet (Users, Log_Aktivitas, Jenis_Kelamin) & admin default siap")
    except Exception as exc:  # noqa: BLE001
        logger.error("Gagal menyiapkan struktur sheet saat startup: %s", exc)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
