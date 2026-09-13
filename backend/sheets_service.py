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
import uuid
import re
import bcrypt
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
USERS_SHEET = "Users"
LOG_SHEET = "Log_Aktivitas"

MASTER_SISWA_HEADERS = ["ID_Siswa", "Nama", "Kelas", "Jenis_Kelamin", "Status_Aktif"]
USERS_HEADERS = ["ID_User", "Nama", "Username", "Password_Hash", "Role", "Terakhir_Login"]
LOG_HEADERS = ["Timestamp", "User", "Aksi", "Detail"]

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
def read_master_siswa(include_inactive: bool = False) -> List[Dict[str, str]]:
    """Read rows from 'Master_Siswa'. By default only Status_Aktif == 'Aktif'."""
    rows = _rows_to_dicts(_read_values(MASTER_SISWA_SHEET))
    if include_inactive:
        return rows
    return [
        r for r in rows
        if (r.get("Status_Aktif", "") or "Aktif").strip().lower() == "aktif"
    ]


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


def generate_absensi_for_date(tanggal: str) -> Dict:
    """Append a default 'Hadir' row for every student missing one on `tanggal`.

    Only missing (ID_Siswa, tanggal) combinations are appended — rows already
    edited by a teacher are left untouched. Idempotent: safe to run repeatedly
    (e.g. cron re-fire or server restart) without creating duplicates.
    """
    jam_update = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _SHEETS_LOCK:
        service, spreadsheet_id = _get_service()
        master = _rows_to_dicts(_fetch_values(service, spreadsheet_id, MASTER_SISWA_SHEET))
        absensi_values = _fetch_values(service, spreadsheet_id, ABSENSI_SHEET)

        # Ensure header row exists.
        if not absensi_values:
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{ABSENSI_SHEET}!A1",
                valueInputOption="RAW",
                body={"values": [ABSENSI_HEADERS]},
            ).execute()
            absensi_values = [ABSENSI_HEADERS]

        headers = [h.strip() for h in absensi_values[0]]
        try:
            idx_id = headers.index("ID_Siswa")
            idx_tanggal = headers.index("Tanggal")
        except ValueError as exc:
            raise SheetsError(
                f"Header sheet '{ABSENSI_SHEET}' tidak sesuai. Harus memuat kolom: "
                f"{', '.join(ABSENSI_HEADERS)}.",
                code="invalid_absensi_headers",
            ) from exc

        # Students who already have a row for this date.
        existing_ids = set()
        for row in absensi_values[1:]:
            padded = row + [""] * (len(headers) - len(row))
            if padded[idx_tanggal].strip() == tanggal.strip():
                existing_ids.add(padded[idx_id].strip())

        active = [
            s for s in master
            if (s.get("Status_Aktif", "") or "Aktif").strip().lower() == "aktif"
        ]
        new_rows = []
        for s in active:
            sid = str(s.get("ID_Siswa", "")).strip()
            if not sid or sid in existing_ids:
                continue
            new_rows.append(
                [tanggal, sid, s.get("Nama", ""), s.get("Kelas", ""), "Hadir", jam_update, ""]
            )

        if new_rows:
            try:
                service.spreadsheets().values().append(
                    spreadsheetId=spreadsheet_id,
                    range=f"{ABSENSI_SHEET}!A1",
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body={"values": new_rows},
                ).execute()
            except HttpError as exc:
                raise _translate_http_error(exc) from exc
            except Exception as exc:  # noqa: BLE001
                raise SheetsError(
                    f"Gagal generate absensi: {exc}", code="generate_failed"
                ) from exc

    return {
        "tanggal": tanggal,
        "created": len(new_rows),
        "skipped": len(active) - len(new_rows),
        "total_master": len(active),
    }


# ---------------------------------------------------------------------------
# Password hashing (bcrypt) — never store plaintext passwords
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Structure setup: new tabs (Users, Log_Aktivitas) + Master_Siswa column
# ---------------------------------------------------------------------------
def _ensure_sheet(service, spreadsheet_id: str, title: str, headers: List[str]) -> None:
    """Create the tab if missing and ensure its header row. Caller holds the lock."""
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    titles = [s["properties"]["title"] for s in meta.get("sheets", [])]
    if title not in titles:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
        ).execute()
    values = _fetch_values(service, spreadsheet_id, title)
    if not values:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{title}!A1",
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()


def _ensure_master_column(service, spreadsheet_id, master_values, col_name, default_value):
    """Ensure Master_Siswa has `col_name`; fill existing rows with default. Caller holds lock."""
    headers = [h.strip() for h in master_values[0]]
    if col_name in headers:
        return master_values, False
    col_letter = chr(ord("A") + len(headers))
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{MASTER_SISWA_SHEET}!{col_letter}1",
        valueInputOption="RAW",
        body={"values": [[col_name]]},
    ).execute()
    n = len(master_values) - 1
    if n > 0 and default_value is not None:
        if callable(default_value):
            col_vals = [[default_value(i)] for i in range(n)]
        else:
            col_vals = [[default_value] for _ in range(n)]
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{MASTER_SISWA_SHEET}!{col_letter}2",
            valueInputOption="RAW",
            body={"values": col_vals},
        ).execute()
    return _fetch_values(service, spreadsheet_id, MASTER_SISWA_SHEET), True


def ensure_structure() -> Dict:
    """Idempotent: ensure Users & Log_Aktivitas tabs and Master_Siswa columns
    (Jenis_Kelamin, Status_Aktif) exist. Safe to run on every startup.
    """
    with _SHEETS_LOCK:
        service, spreadsheet_id = _get_service()
        _ensure_sheet(service, spreadsheet_id, USERS_SHEET, USERS_HEADERS)
        _ensure_sheet(service, spreadsheet_id, LOG_SHEET, LOG_HEADERS)

        added_columns = []
        master_values = _fetch_values(service, spreadsheet_id, MASTER_SISWA_SHEET)
        if master_values:
            master_values, a1 = _ensure_master_column(
                service, spreadsheet_id, master_values, "Jenis_Kelamin",
                lambda i: ["Laki-laki", "Perempuan"][i % 2],
            )
            master_values, a2 = _ensure_master_column(
                service, spreadsheet_id, master_values, "Status_Aktif", "Aktif"
            )
            if a1:
                added_columns.append("Jenis_Kelamin")
            if a2:
                added_columns.append("Status_Aktif")
    return {"added_columns": added_columns}


# ---------------------------------------------------------------------------
# Users sheet: basic READ / WRITE (login endpoints come later)
# ---------------------------------------------------------------------------
def read_users() -> List[Dict[str, str]]:
    """Read all rows from the 'Users' sheet as list of dicts (includes Password_Hash)."""
    return _rows_to_dicts(_read_values(USERS_SHEET))


def write_user(
    nama: str,
    username: str,
    password_hash: str,
    role: str = "guru",
    terakhir_login: str = "",
    id_user: Optional[str] = None,
) -> Dict:
    """Insert or update one user row keyed by Username (no duplicate usernames)."""
    with _SHEETS_LOCK:
        service, spreadsheet_id = _get_service()
        values = _fetch_values(service, spreadsheet_id, USERS_SHEET)
        if not values:
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{USERS_SHEET}!A1",
                valueInputOption="RAW",
                body={"values": [USERS_HEADERS]},
            ).execute()
            values = [USERS_HEADERS]

        headers = [h.strip() for h in values[0]]
        idx_username = headers.index("Username")
        idx_id = headers.index("ID_User")

        target_row = None
        existing_id = None
        for i, row in enumerate(values[1:], start=2):
            padded = row + [""] * (len(headers) - len(row))
            if padded[idx_username].strip() == username.strip():
                target_row = i
                existing_id = padded[idx_id].strip()
                break

        uid = id_user or existing_id or str(uuid.uuid4())
        new_row = [uid, nama, username, password_hash, role, terakhir_login]

        if target_row:
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{USERS_SHEET}!A{target_row}",
                valueInputOption="RAW",
                body={"values": [new_row]},
            ).execute()
            action = "updated"
        else:
            service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=f"{USERS_SHEET}!A1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [new_row]},
            ).execute()
            action = "appended"

    return {"action": action, "row": dict(zip(USERS_HEADERS, new_row))}


def seed_default_admin(username: str, password: str, nama: str = "Administrator", role: str = "admin") -> Dict:
    """Create the default admin (hashed password) only if that username has none yet."""
    users = read_users()
    existing = next((u for u in users if u.get("Username", "").strip() == username), None)
    if existing and existing.get("Password_Hash", "").strip():
        return {"created": False}
    write_user(nama=nama, username=username, password_hash=hash_password(password), role=role)
    return {"created": True}


# ---------------------------------------------------------------------------
# Activity log
# ---------------------------------------------------------------------------
def append_log(user: str, aksi: str, detail: str) -> bool:
    """Append one row to 'Log_Aktivitas' (Timestamp, User, Aksi, Detail)."""
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _SHEETS_LOCK:
        service, spreadsheet_id = _get_service()
        values = _fetch_values(service, spreadsheet_id, LOG_SHEET)
        if not values:
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{LOG_SHEET}!A1",
                valueInputOption="RAW",
                body={"values": [LOG_HEADERS]},
            ).execute()
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{LOG_SHEET}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [[ts, user, aksi, detail]]},
        ).execute()
    return True


# ---------------------------------------------------------------------------
# Master_Siswa CRUD (soft-delete via Status_Aktif)
# ---------------------------------------------------------------------------
def _find_master_row(values, headers, id_siswa):
    idx_id = headers.index("ID_Siswa")
    for i, row in enumerate(values[1:], start=2):
        padded = row + [""] * (len(headers) - len(row))
        if padded[idx_id].strip() == id_siswa.strip():
            return i, padded
    return None, None


def create_siswa(nama: str, kelas: str, jenis_kelamin: str) -> Dict:
    """Append a new active student with an auto-generated unique ID_Siswa (S###)."""
    with _SHEETS_LOCK:
        service, spreadsheet_id = _get_service()
        values = _fetch_values(service, spreadsheet_id, MASTER_SISWA_SHEET)
        if not values:
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{MASTER_SISWA_SHEET}!A1",
                valueInputOption="RAW",
                body={"values": [MASTER_SISWA_HEADERS]},
            ).execute()
            values = [MASTER_SISWA_HEADERS]

        headers = [h.strip() for h in values[0]]
        idx_id = headers.index("ID_Siswa")
        max_n = 0
        for row in values[1:]:
            rid = (row[idx_id] if len(row) > idx_id else "").strip()
            m = re.match(r"^S(\d+)$", rid)
            if m:
                max_n = max(max_n, int(m.group(1)))
        new_id = f"S{max_n + 1:03d}"

        record = {
            "ID_Siswa": new_id, "Nama": nama, "Kelas": kelas,
            "Jenis_Kelamin": jenis_kelamin, "Status_Aktif": "Aktif",
        }
        new_row = [record.get(h, "") for h in headers]
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{MASTER_SISWA_SHEET}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [new_row]},
        ).execute()
    return {"id_siswa": new_id, "row": record}


def update_siswa(id_siswa: str, nama: str, kelas: str, jenis_kelamin: str) -> Dict:
    """Update Nama/Kelas/Jenis_Kelamin of an existing student (preserves other columns)."""
    with _SHEETS_LOCK:
        service, spreadsheet_id = _get_service()
        values = _fetch_values(service, spreadsheet_id, MASTER_SISWA_SHEET)
        headers = [h.strip() for h in values[0]] if values else MASTER_SISWA_HEADERS
        row_num, padded = _find_master_row(values, headers, id_siswa)
        if not row_num:
            raise SheetsError(f"Siswa {id_siswa} tidak ditemukan.", code="student_not_found")

        existing = {h: padded[i] for i, h in enumerate(headers)}
        old = {
            "Nama": existing.get("Nama", ""),
            "Kelas": existing.get("Kelas", ""),
            "Jenis_Kelamin": existing.get("Jenis_Kelamin", ""),
        }
        updated = dict(existing)
        updated["Nama"] = nama
        updated["Kelas"] = kelas
        updated["Jenis_Kelamin"] = jenis_kelamin
        new_row = [updated.get(h, "") for h in headers]
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{MASTER_SISWA_SHEET}!A{row_num}",
            valueInputOption="RAW",
            body={"values": [new_row]},
        ).execute()
    return {"id_siswa": id_siswa, "old": old, "row": updated}


def set_siswa_status(id_siswa: str, status_aktif: str) -> Dict:
    """Soft delete / reactivate: set Status_Aktif for a student."""
    with _SHEETS_LOCK:
        service, spreadsheet_id = _get_service()
        values = _fetch_values(service, spreadsheet_id, MASTER_SISWA_SHEET)
        headers = [h.strip() for h in values[0]] if values else MASTER_SISWA_HEADERS
        if "Status_Aktif" not in headers:
            raise SheetsError("Kolom Status_Aktif belum ada di Master_Siswa.", code="missing_status_column")
        row_num, padded = _find_master_row(values, headers, id_siswa)
        if not row_num:
            raise SheetsError(f"Siswa {id_siswa} tidak ditemukan.", code="student_not_found")

        updated = {h: padded[i] for i, h in enumerate(headers)}
        updated["Status_Aktif"] = status_aktif
        new_row = [updated.get(h, "") for h in headers]
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{MASTER_SISWA_SHEET}!A{row_num}",
            valueInputOption="RAW",
            body={"values": [new_row]},
        ).execute()
    return {"id_siswa": id_siswa, "nama": updated.get("Nama", ""), "status_aktif": status_aktif, "row": updated}
