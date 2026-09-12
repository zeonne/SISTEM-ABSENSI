from fastapi import FastAPI, APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
from pathlib import Path
from typing import List, Optional

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import sheets_service
from sheets_service import SheetsError

# MongoDB connection (kept from foundation; used for app-level metadata later)
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

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


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
