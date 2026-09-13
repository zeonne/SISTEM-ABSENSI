"""
Google Sheets service-account integration for the Sistem Absensi Sekolah app.

Design goals:
- Non-interactive: uses a Google service account (server-to-server), no OAuth prompts.
- Clear, informative errors (raised as SheetsError) instead of silent crashes.
- Easy to extend in later stages (status update, daily generation, class filter).

Configuration (via backend/.env):
- GOOGLE_SERVICE_ACCOUNT_FILE : absolute path to the service account JSON key file.
- GOOGLE_SPREADSHEET_ID       : the ID of the target Google Spreadsheet.
"""

import os
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# googleapiclient's Http object is NOT thread-safe. Since /api routes are
# offloaded via asyncio.to_thread, concurrent requests can share the same
# cached Http socket and cause SSL: WRONG_VERSION_NUMBER errors (and even
# glibc heap corruption). Serialize all Sheets API calls with this lock.
_SHEETS_LOCK = threading.Lock()

logger = logging.getLogger(__name__)

# Read/write scope is required because we also update the "Absensi" sheet.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

MASTER_SISWA_SHEET = "Master_Siswa"
ABSENSI_SHEET = "Absensi"

# Canonical column order for the Absensi sheet.
ABSENSI_HEADERS = [
    "Tanggal",
    "ID_Siswa",
    "Nama",
    "Kelas",
    "Status",
    "Jam_Update",
    "Keterangan",
]


class SheetsError(Exception):
    """Raised for any Google Sheets configuration/connection/operation failure.

    Attributes:
        message: human-readable, actionable message (safe to show the user).
        code:    short machine code to help the frontend react.
    """

    def __init__(self, message: str, code: str = "sheets_error"):
        super().__init__(message)
        self.message = message
        self.code = code


# Cache the built Sheets client so we don't refetch discovery / rebuild creds per request.
_SERVICE_CACHE = {"key": None, "service": None, "spreadsheet_id": None}


def _get_config():
    sa_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    spreadsheet_id = os.environ.get("GOOGLE_SPREADSHEET_ID", "").strip()
    return sa_file, spreadsheet_id


def get_service_account_email() -> Optional[str]:
    """Return the service account's client_email from the key file, or None if unavailable."""
    sa_file, _ = _get_config()
    if not sa_file:
        return None
    try:
        data = json.loads(Path(sa_file).read_text())
        return data.get("client_email")
    except Exception as exc:  # noqa: BLE001 - want a safe None here
        logger.warning("Could not read service account email: %s", exc)
        return None


def get_config_status() -> Dict:
    """Report configuration state so the UI can guide the user through setup."""
    sa_file, spreadsheet_id = _get_config()
    file_exists = bool(sa_file) and Path(sa_file).exists()
    return {
        "service_account_configured": file_exists,
        "service_account_email": get_service_account_email() if file_exists else None,
        "spreadsheet_configured": bool(spreadsheet_id),
    }


def _get_service():
    """Build an authenticated Sheets API client. Raises SheetsError on any problem."""
    sa_file, spreadsheet_id = _get_config()

    if not sa_file:
        raise SheetsError(
            "GOOGLE_SERVICE_ACCOUNT_FILE belum diatur. Unggah file kunci JSON service account "
            "dan set path-nya di backend/.env.",
            code="missing_service_account_config",
        )
    if not Path(sa_file).exists():
        raise SheetsError(
            f"File service account tidak ditemukan di path: {sa_file}. "
            "Pastikan file JSON sudah diunggah ke path tersebut.",
            code="service_account_file_not_found",
        )
    if not spreadsheet_id:
        raise SheetsError(
            "GOOGLE_SPREADSHEET_ID belum diatur di backend/.env. "
            "Berikan ID spreadsheet setelah men-share sheet ke email service account.",
            code="missing_spreadsheet_id",
        )

    try:
        creds = service_account.Credentials.from_service_account_file(
            sa_file, scopes=SCOPES
        )
    except Exception as exc:  # noqa: BLE001
        raise SheetsError(
            f"Gagal membaca kredensial service account: {exc}. "
            "Pastikan file JSON valid dan tidak rusak.",
            code="invalid_service_account_file",
        ) from exc

    # Return cached client if config is unchanged.
    cache_key = (sa_file, spreadsheet_id, os.path.getmtime(sa_file))
    if _SERVICE_CACHE["key"] == cache_key and _SERVICE_CACHE["service"] is not None:
        return _SERVICE_CACHE["service"], spreadsheet_id

    try:
        # static_discovery=True uses the bundled discovery doc (no per-request network fetch).
        service = build(
            "sheets",
            "v4",
            credentials=creds,
            cache_discovery=False,
            static_discovery=True,
        )
    except Exception as exc:  # noqa: BLE001
        raise SheetsError(
            f"Gagal membangun koneksi ke Google Sheets API: {exc}",
            code="build_service_failed",
        ) from exc

    _SERVICE_CACHE.update(key=cache_key, service=service, spreadsheet_id=spreadsheet_id)
    return service, spreadsheet_id


def _translate_http_error(exc: HttpError) -> SheetsError:
    """Map Google API HttpError into a friendly, actionable SheetsError."""
    status = getattr(getattr(exc, "resp", None), "status", None)
    if status == 403:
        email = get_service_account_email() or "(email service account)"
        return SheetsError(
            f"Akses ditolak (403). Pastikan spreadsheet sudah di-share ke {email} "
            "sebagai Editor, dan Google Sheets API sudah diaktifkan di project.",
            code="permission_denied",
        )
    if status == 404:
        return SheetsError(
            "Spreadsheet tidak ditemukan (404). Periksa kembali GOOGLE_SPREADSHEET_ID.",
            code="spreadsheet_not_found",
        )
    if status == 400:
        return SheetsError(
            "Permintaan tidak valid (400). Kemungkinan nama sheet salah "
            f"(harus persis '{MASTER_SISWA_SHEET}' dan '{ABSENSI_SHEET}').",
            code="bad_request",
        )
    return SheetsError(
        f"Google Sheets API error: {exc}",
        code="google_api_error",
    )


def _rows_to_dicts(values: List[List[str]]) -> List[Dict[str, str]]:
    """Convert a raw values matrix (first row = headers) into a list of dicts."""
    if not values:
        return []
    headers = [h.strip() for h in values[0]]
    result: List[Dict[str, str]] = []
    for row in values[1:]:
        # Pad short rows so every header has a value.
        padded = row + [""] * (len(headers) - len(row))
        result.append({headers[i]: padded[i] for i in range(len(headers))})
    return result


def _fetch_values(service, spreadsheet_id: str, sheet_name: str) -> List[List[str]]:
    """Fetch raw values for a sheet. Caller MUST already hold _SHEETS_LOCK."""
    try:
        resp = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=sheet_name)
            .execute()
        )
    except HttpError as exc:
        raise _translate_http_error(exc) from exc
    except Exception as exc:  # noqa: BLE001
        raise SheetsError(
            f"Koneksi ke Google Sheets gagal: {exc}", code="connection_failed"
        ) from exc
    return resp.get("values", [])


def _read_values(sheet_name: str) -> List[List[str]]:
    with _SHEETS_LOCK:
        service, spreadsheet_id = _get_service()
        return _fetch_values(service, spreadsheet_id, sheet_name)


# ---------------------------------------------------------------------------
# READ functions
# ---------------------------------------------------------------------------
def read_master_siswa() -> List[Dict[str, str]]:
    """Read all rows from the 'Master_Siswa' sheet as list of dicts."""
    return _rows_to_dicts(_read_values(MASTER_SISWA_SHEET))


def read_absensi(tanggal: Optional[str] = None) -> List[Dict[str, str]]:
    """Read all rows from the 'Absensi' sheet, optionally filtered by Tanggal (YYYY-MM-DD)."""
    rows = _rows_to_dicts(_read_values(ABSENSI_SHEET))
    if tanggal:
        rows = [r for r in rows if r.get("Tanggal", "").strip() == tanggal.strip()]
    return rows


# ---------------------------------------------------------------------------
# WRITE function
# ---------------------------------------------------------------------------
def write_absensi_row(
    id_siswa: str,
    tanggal: str,
    nama: str = "",
    kelas: str = "",
    status: str = "Hadir",
    keterangan: str = "",
) -> Dict:
    """Insert or update a single row in 'Absensi' keyed by (ID_Siswa, Tanggal).

    If a matching (ID_Siswa, Tanggal) row exists it is updated in place,
    otherwise a new row is appended. Jam_Update is set to the current UTC time.
    """
    jam_update = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new_row = [tanggal, id_siswa, nama, kelas, status, jam_update, keterangan]

    # Read + write atomically under one lock so concurrent updates to the same
    # (ID_Siswa, Tanggal) can never create duplicate rows.
    with _SHEETS_LOCK:
        service, spreadsheet_id = _get_service()

        # Read existing values to locate a matching row.
        values = _fetch_values(service, spreadsheet_id, ABSENSI_SHEET)

        # Ensure header row exists.
        if not values:
            try:
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"{ABSENSI_SHEET}!A1",
                    valueInputOption="RAW",
                    body={"values": [ABSENSI_HEADERS]},
                ).execute()
            except HttpError as exc:
                raise _translate_http_error(exc) from exc
            values = [ABSENSI_HEADERS]

        headers = [h.strip() for h in values[0]]
        try:
            idx_id = headers.index("ID_Siswa")
            idx_tanggal = headers.index("Tanggal")
        except ValueError as exc:
            raise SheetsError(
                f"Header sheet '{ABSENSI_SHEET}' tidak sesuai. Harus memuat kolom: "
                f"{', '.join(ABSENSI_HEADERS)}.",
                code="invalid_absensi_headers",
            ) from exc

        target_row_number = None  # 1-based sheet row number
        for i, row in enumerate(values[1:], start=2):
            padded = row + [""] * (len(headers) - len(row))
            if (
                padded[idx_id].strip() == id_siswa.strip()
                and padded[idx_tanggal].strip() == tanggal.strip()
            ):
                target_row_number = i
                break

        try:
            if target_row_number:
                rng = f"{ABSENSI_SHEET}!A{target_row_number}"
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=rng,
                    valueInputOption="RAW",
                    body={"values": [new_row]},
                ).execute()
                action = "updated"
            else:
                service.spreadsheets().values().append(
                    spreadsheetId=spreadsheet_id,
                    range=f"{ABSENSI_SHEET}!A1",
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body={"values": [new_row]},
                ).execute()
                action = "appended"
        except HttpError as exc:
            raise _translate_http_error(exc) from exc
        except Exception as exc:  # noqa: BLE001
            raise SheetsError(
                f"Gagal menulis ke Google Sheets: {exc}", code="write_failed"
            ) from exc

    return {"action": action, "row": dict(zip(ABSENSI_HEADERS, new_row))}
