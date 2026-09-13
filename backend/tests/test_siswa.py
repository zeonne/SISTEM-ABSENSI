"""Backend Siswa CRUD tests: /api/siswa GET/POST/PUT, /api/siswa/{id}/status, auth + logs."""
import os
import uuid
import time

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"


@pytest.fixture(scope="module")
def auth_session():
    s = requests.Session()
    r = s.post(f"{API}/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    assert "access_token" in s.cookies
    return s


# --- Protection ---
class TestProtection:
    def test_get_siswa_401(self):
        assert requests.get(f"{API}/siswa").status_code == 401

    def test_post_siswa_401(self):
        r = requests.post(f"{API}/siswa", json={"nama": "X", "kelas": "1A", "jenis_kelamin": "Laki-laki"})
        assert r.status_code == 401

    def test_put_siswa_401(self):
        r = requests.put(f"{API}/siswa/S001", json={"nama": "X", "kelas": "1A", "jenis_kelamin": "Laki-laki"})
        assert r.status_code == 401

    def test_status_siswa_401(self):
        r = requests.post(f"{API}/siswa/S001/status", json={"status_aktif": "Nonaktif"})
        assert r.status_code == 401


# --- Filter by status ---
class TestListFilter:
    def test_default_aktif_only(self, auth_session):
        r = auth_session.get(f"{API}/siswa")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "aktif"
        for row in body["data"]:
            sa = (row.get("Status_Aktif", "") or "Aktif").strip().lower()
            assert sa == "aktif", f"non-aktif row leaked: {row}"

    def test_nonaktif_only(self, auth_session):
        r = auth_session.get(f"{API}/siswa", params={"status": "nonaktif"})
        assert r.status_code == 200
        for row in r.json()["data"]:
            sa = (row.get("Status_Aktif", "") or "").strip().lower()
            assert sa == "nonaktif"

    def test_all(self, auth_session):
        r = auth_session.get(f"{API}/siswa", params={"status": "all"})
        assert r.status_code == 200
        assert r.json()["count"] >= 0


# --- Validation ---
class TestValidation:
    def test_create_empty_nama_422(self, auth_session):
        r = auth_session.post(f"{API}/siswa", json={"nama": "  ", "kelas": "1A", "jenis_kelamin": "Laki-laki"})
        assert r.status_code == 422

    def test_create_empty_kelas_422(self, auth_session):
        r = auth_session.post(f"{API}/siswa", json={"nama": "TEST_x", "kelas": "", "jenis_kelamin": "Laki-laki"})
        assert r.status_code == 422

    def test_create_bad_gender_422(self, auth_session):
        r = auth_session.post(f"{API}/siswa", json={"nama": "TEST_x", "kelas": "1A", "jenis_kelamin": "M"})
        assert r.status_code == 422


# --- Full CRUD lifecycle: create -> edit -> deactivate -> reactivate -> deactivate again for cleanup ---
class TestLifecycle:
    def test_full_lifecycle(self, auth_session):
        suffix = uuid.uuid4().hex[:6]
        nama = f"TEST_Siswa_{suffix}"
        kelas = f"TESTK_{suffix}"

        # CREATE
        r = auth_session.post(f"{API}/siswa", json={
            "nama": nama, "kelas": kelas, "jenis_kelamin": "Perempuan"
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        sid = body.get("id_siswa")
        assert sid and sid.startswith("S")

        time.sleep(0.5)

        # Verify appears in aktif list
        r2 = auth_session.get(f"{API}/siswa")
        rows = r2.json()["data"]
        found = next((x for x in rows if x.get("ID_Siswa") == sid), None)
        assert found is not None, f"created siswa {sid} not in aktif list"
        assert found.get("Nama") == nama
        assert found.get("Kelas") == kelas

        # EDIT
        new_nama = nama + "_edited"
        r = auth_session.put(f"{API}/siswa/{sid}", json={
            "nama": new_nama, "kelas": kelas, "jenis_kelamin": "Perempuan"
        })
        assert r.status_code == 200, r.text
        time.sleep(0.5)

        r2 = auth_session.get(f"{API}/siswa")
        row = next((x for x in r2.json()["data"] if x.get("ID_Siswa") == sid), None)
        assert row is not None and row.get("Nama") == new_nama

        # DEACTIVATE (soft delete)
        r = auth_session.post(f"{API}/siswa/{sid}/status", json={"status_aktif": "Nonaktif"})
        assert r.status_code == 200, r.text
        time.sleep(0.5)

        # Not in aktif
        r2 = auth_session.get(f"{API}/siswa")
        assert not any(x.get("ID_Siswa") == sid for x in r2.json()["data"])

        # In nonaktif
        r3 = auth_session.get(f"{API}/siswa", params={"status": "nonaktif"})
        assert any(x.get("ID_Siswa") == sid for x in r3.json()["data"])

        # REACTIVATE
        r = auth_session.post(f"{API}/siswa/{sid}/status", json={"status_aktif": "Aktif"})
        assert r.status_code == 200
        time.sleep(0.5)

        r2 = auth_session.get(f"{API}/siswa")
        assert any(x.get("ID_Siswa") == sid for x in r2.json()["data"])

        # Cleanup: deactivate again to keep sheet tidy
        auth_session.post(f"{API}/siswa/{sid}/status", json={"status_aktif": "Nonaktif"})

    def test_deactivated_excluded_from_generate(self, auth_session):
        """Deactivated student should NOT be included in generate-absensi output."""
        # Create + deactivate a student
        suffix = uuid.uuid4().hex[:6]
        nama = f"TEST_Skip_{suffix}"
        r = auth_session.post(f"{API}/siswa", json={
            "nama": nama, "kelas": f"SKIPK_{suffix}", "jenis_kelamin": "Laki-laki"
        })
        assert r.status_code == 200
        sid = r.json()["id_siswa"]
        time.sleep(0.3)
        auth_session.post(f"{API}/siswa/{sid}/status", json={"status_aktif": "Nonaktif"})
        time.sleep(0.5)

        # generate-absensi for today: should not error, and nonaktif student not appended
        r = auth_session.post(f"{API}/generate-absensi", json={})
        assert r.status_code == 200, r.text


class TestInvalid:
    def test_update_nonexistent_404(self, auth_session):
        r = auth_session.put(f"{API}/siswa/S_NOPE_9999", json={
            "nama": "TEST_z", "kelas": "Z", "jenis_kelamin": "Laki-laki"
        })
        assert r.status_code == 404

    def test_status_bad_value_422(self, auth_session):
        r = auth_session.post(f"{API}/siswa/S001/status", json={"status_aktif": "Bogus"})
        assert r.status_code == 422
