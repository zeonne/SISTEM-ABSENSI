"""Backend tests for the new generate-absensi (manual + cron) endpoints."""
import os
import subprocess

import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://roll-call-app-158.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"

# Today in Asia/Jakarta as used by the backend's today_local()
TODAY = subprocess.check_output(
    ["date", "+%F"], env={**os.environ, "TZ": "Asia/Jakarta"}
).decode().strip()

# Cron secret read from backend .env (must match server-side).
def _read_cron_secret():
    env_path = "/app/backend/.env"
    with open(env_path) as f:
        for line in f:
            if line.startswith("WEBHOOK_CRON_SECRET"):
                _, _, v = line.partition("=")
                return v.strip().strip('"').strip("'")
    return ""


CRON_SECRET = _read_cron_secret()

EXPECTED_STUDENTS = {"S001", "S002", "S003", "S004", "S005"}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# -- Manual generate --
def test_generate_absensi_creates_missing_rows(client):
    r = client.post(f"{API}/generate-absensi", json={"tanggal": TODAY})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["tanggal"] == TODAY
    assert body["total_master"] >= 5
    # created + skipped should equal total_master
    assert body["created"] + body["skipped"] == body["total_master"]

    # After first run, verify all EXPECTED_STUDENTS have a row for today.
    r2 = client.get(f"{API}/absensi", params={"tanggal": TODAY})
    assert r2.status_code == 200
    ids_today = {row["ID_Siswa"] for row in r2.json()["data"]}
    assert EXPECTED_STUDENTS.issubset(ids_today)


def test_generate_absensi_idempotent_no_duplicates(client):
    # Second invocation should create 0 (all already exist).
    r = client.post(f"{API}/generate-absensi", json={"tanggal": TODAY})
    assert r.status_code == 200
    body = r.json()
    assert body["created"] == 0
    assert body["skipped"] == body["total_master"]

    # And GET should still return exactly one row per student for today.
    r2 = client.get(f"{API}/absensi", params={"tanggal": TODAY})
    rows = r2.json()["data"]
    for sid in EXPECTED_STUDENTS:
        matches = [row for row in rows if row["ID_Siswa"] == sid]
        assert len(matches) == 1, f"Duplicate rows for {sid}: {len(matches)}"


def test_generate_does_not_overwrite_manual_edit(client):
    # Set S002 -> Sakit manually.
    r = client.post(f"{API}/absensi", json={
        "id_siswa": "S002", "tanggal": TODAY, "nama": "Siti Nurhaliza",
        "kelas": "6A", "status": "Sakit", "keterangan": "flu",
    })
    assert r.status_code == 200

    # Run generate again — should NOT overwrite S002.
    r2 = client.post(f"{API}/generate-absensi", json={"tanggal": TODAY})
    assert r2.status_code == 200
    assert r2.json()["created"] == 0

    # Verify S002 is still Sakit.
    r3 = client.get(f"{API}/absensi", params={"tanggal": TODAY})
    row = next(x for x in r3.json()["data"] if x["ID_Siswa"] == "S002")
    assert row["Status"] == "Sakit"
    assert row["Keterangan"] == "flu"


def test_generate_defaults_to_today_when_no_body(client):
    # No JSON body — server should default to today_local().
    r = client.post(f"{API}/generate-absensi")
    assert r.status_code == 200, r.text
    assert r.json()["tanggal"] == TODAY


# -- Cron endpoint auth --
def test_cron_no_auth_returns_401(client):
    # Use a fresh session to avoid the module-level Authorization header.
    r = requests.post(f"{API}/cron/generate-absensi")
    assert r.status_code == 401


def test_cron_wrong_token_returns_401(client):
    r = requests.post(
        f"{API}/cron/generate-absensi",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert r.status_code == 401


def test_cron_valid_token_returns_200(client):
    assert CRON_SECRET, "WEBHOOK_CRON_SECRET missing from backend/.env"
    r = requests.post(
        f"{API}/cron/generate-absensi",
        headers={"Authorization": f"Bearer {CRON_SECRET}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    assert body.get("accepted") is True
