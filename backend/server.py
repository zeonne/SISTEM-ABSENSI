from fastapi import FastAPI, APIRouter, HTTPException, Query, BackgroundTasks, Header, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import hmac
import logging
import asyncio
from datetime import datetime
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


@api_router.get("/siswa")
async def get_siswa():
    """Return all rows from the 'Master_Siswa' sheet."""
    try:
        data = await asyncio.to_thread(sheets_service.read_master_siswa)
        return {"data": data, "count": len(data)}
    except SheetsError as exc:
        logger.error("Gagal membaca Master_Siswa: %s", exc.message)
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message})


@api_router.get("/absensi")
async def get_absensi(tanggal: Optional[str] = Query(None, description="Filter tanggal YYYY-MM-DD")):
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
async def upsert_absensi(payload: AbsensiUpdate):
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
async def generate_absensi(payload: GenerateRequest = GenerateRequest()):
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
