"""Backend API tests for Sistem Absensi Sekolah."""
import os
from datetime import date

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://roll-call-app-158.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
TODAY = date.today().isoformat()

EXPECTED_STUDENTS = {"S001", "S002", "S003", "S004", "S005"}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# -- Health --
def test_root(client):
    r = client.get(f"{API}/")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_sheets_config(client):
    r = client.get(f"{API}/config/sheets")
    assert r.status_code == 200
    data = r.json()
    assert data["service_account_configured"] is True
    assert data["spreadsheet_configured"] is True


# -- Master Siswa --
def test_get_siswa(client):
    r = client.get(f"{API}/siswa")
    assert r.status_code == 200
    body = r.json()
    ids = {s["ID_Siswa"] for s in body["data"]}
    assert EXPECTED_STUDENTS.issubset(ids), f"Expected {EXPECTED_STUDENTS}, got {ids}"


# -- Absensi CRUD (upsert) --
def test_get_absensi_today(client):
    r = client.get(f"{API}/absensi", params={"tanggal": TODAY})
    assert r.status_code == 200
    assert "data" in r.json()


def test_upsert_invalid_status_returns_422(client):
    r = client.post(f"{API}/absensi", json={
        "id_siswa": "S001", "tanggal": TODAY, "nama": "Ahmad", "kelas": "X",
        "status": "Bolos", "keterangan": ""
    })
    assert r.status_code == 422
    detail = r.json().get("detail", {})
    assert isinstance(detail, dict)
    assert "message" in detail
    assert detail.get("code") == "invalid_status"


def test_upsert_missing_id_returns_422(client):
    r = client.post(f"{API}/absensi", json={
        "id_siswa": "", "tanggal": TODAY, "nama": "X", "kelas": "X",
        "status": "Hadir", "keterangan": ""
    })
    assert r.status_code == 422


def test_upsert_updates_existing_no_duplicate(client):
    # Write S002 -> Sakit
    r1 = client.post(f"{API}/absensi", json={
        "id_siswa": "S002", "tanggal": TODAY, "nama": "Siti Nurhaliza",
        "kelas": "X-A", "status": "Sakit", "keterangan": "flu"
    })
    assert r1.status_code == 200, r1.text
    # Write S002 -> Pulang
    r2 = client.post(f"{API}/absensi", json={
        "id_siswa": "S002", "tanggal": TODAY, "nama": "Siti Nurhaliza",
        "kelas": "X-A", "status": "Pulang", "keterangan": "acara"
    })
    assert r2.status_code == 200
    # GET absensi today: only one row for S002 with latest status
    r3 = client.get(f"{API}/absensi", params={"tanggal": TODAY})
    rows = [x for x in r3.json()["data"] if x.get("ID_Siswa") == "S002"]
    assert len(rows) == 1, f"Expected 1 row for S002, got {len(rows)}"
    assert rows[0]["Status"] == "Pulang"
    assert rows[0]["Keterangan"] == "acara"


def test_upsert_keterangan_persists(client):
    r = client.post(f"{API}/absensi", json={
        "id_siswa": "S001", "tanggal": TODAY, "nama": "Ahmad Fauzi",
        "kelas": "X-A", "status": "Sakit", "keterangan": "demam tinggi"
    })
    assert r.status_code == 200
    r2 = client.get(f"{API}/absensi", params={"tanggal": TODAY})
    row = next((x for x in r2.json()["data"] if x["ID_Siswa"] == "S001"), None)
    assert row is not None
    assert row["Status"] == "Sakit"
    assert row["Keterangan"] == "demam tinggi"


def test_all_valid_statuses(client):
    for status in ["Hadir", "Sakit", "Ijin", "Pulang"]:
        r = client.post(f"{API}/absensi", json={
            "id_siswa": "S003", "tanggal": TODAY, "nama": "Budi Santoso",
            "kelas": "X-A", "status": status, "keterangan": ""
        })
        assert r.status_code == 200, f"Status {status} failed: {r.text}"
