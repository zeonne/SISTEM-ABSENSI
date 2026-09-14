"""Backend tests for new endpoints:
- GET /api/logs (auth-protected; returns Log_Aktivitas rows with expected keys)
- GET /api/dashboard?kelas=... (returns kelas_list; filters stats to the selected class)
"""
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_USER = "admin"
ADMIN_PASS = "admin123"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{API}/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    if r.status_code != 200:
        pytest.skip(f"Login failed ({r.status_code}): {r.text}")
    yield s
    try:
        s.post(f"{API}/logout")
    except Exception:
        pass


# --- /api/logs ---
class TestLogs:
    def test_logs_requires_auth(self):
        r = requests.get(f"{API}/logs")
        assert r.status_code == 401

    def test_logs_returns_expected_shape(self, session):
        r = session.get(f"{API}/logs")
        assert r.status_code == 200
        body = r.json()
        assert "data" in body and "count" in body
        assert isinstance(body["data"], list)
        assert body["count"] == len(body["data"])
        if body["data"]:
            row = body["data"][0]
            for key in ("Timestamp", "User", "Aksi", "Detail"):
                assert key in row, f"missing key {key} in log row: {row}"

    def test_logs_contains_login_action(self, session):
        # We just logged in via the fixture -> at least one 'Login' entry should exist
        r = session.get(f"{API}/logs")
        assert r.status_code == 200
        rows = r.json()["data"]
        aksi_values = {(r.get("Aksi") or "").strip() for r in rows}
        assert "Login" in aksi_values


# --- /api/dashboard kelas filter ---
class TestDashboardKelas:
    def test_dashboard_returns_kelas_list_without_filter(self, session):
        r = session.get(f"{API}/dashboard")
        assert r.status_code == 200
        body = r.json()
        assert "kelas_list" in body
        assert isinstance(body["kelas_list"], list)
        # Expect duplicates removed & sorted
        assert body["kelas_list"] == sorted(set(body["kelas_list"]))

    def test_dashboard_kelas_filter_scopes_stats(self, session):
        # Baseline
        r_all = session.get(f"{API}/dashboard").json()
        kelas_list = r_all.get("kelas_list") or []
        if not kelas_list:
            pytest.skip("No classes in active students")
        target = kelas_list[0]

        r = session.get(f"{API}/dashboard", params={"kelas": target})
        assert r.status_code == 200
        body = r.json()
        # perhatian rows should all be for the selected class
        for row in body.get("perhatian", []):
            assert row.get("Kelas") == target, row
        # total_aktif must be <= total (baseline)
        assert body["total_aktif"] <= r_all["total_aktif"]
        # sum of gender counts must equal total_aktif
        g = body["gender"]
        assert g["Laki-laki"] + g["Perempuan"] == body["total_aktif"]
        # kelas_list still exposed
        assert isinstance(body["kelas_list"], list)

    def test_dashboard_semua_kelas_matches_no_param(self, session):
        r1 = session.get(f"{API}/dashboard").json()
        r2 = session.get(f"{API}/dashboard", params={"kelas": "Semua"}).json()
        assert r1["total_aktif"] == r2["total_aktif"]
        assert r1["gender"] == r2["gender"]

    def test_dashboard_unknown_kelas_returns_zero(self, session):
        r = session.get(f"{API}/dashboard", params={"kelas": "NOT_A_REAL_CLASS_ZZZ"})
        assert r.status_code == 200
        body = r.json()
        assert body["total_aktif"] == 0
        assert body["gender"] == {"Laki-laki": 0, "Perempuan": 0}
        assert body["perhatian"] == []
