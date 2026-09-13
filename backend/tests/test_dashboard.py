"""Backend tests for GET /api/dashboard (Dashboard stage)."""
import os
from datetime import date

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
TODAY = date.today().isoformat()

ADMIN_USER = "admin"
ADMIN_PASS = "admin123"


@pytest.fixture(scope="module")
def auth_session():
    s = requests.Session()
    r = s.post(f"{API}/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    return s


class TestDashboardProtection:
    def test_401_no_auth(self):
        r = requests.get(f"{API}/dashboard")
        assert r.status_code == 401


class TestDashboardShape:
    def test_dashboard_returns_expected_shape(self, auth_session):
        r = auth_session.get(f"{API}/dashboard")
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("tanggal", "kehadiran", "gender", "perhatian", "total_aktif"):
            assert k in body, f"missing key {k}"
        assert body["tanggal"]  # default today
        keh = body["kehadiran"]
        for k in ("Hadir", "Sakit", "Ijin", "Pulang"):
            assert k in keh and isinstance(keh[k], int) and keh[k] >= 0
        g = body["gender"]
        assert "Laki-laki" in g and "Perempuan" in g
        assert isinstance(g["Laki-laki"], int) and isinstance(g["Perempuan"], int)
        assert isinstance(body["perhatian"], list)
        assert isinstance(body["total_aktif"], int)

    def test_dashboard_respects_tanggal_query(self, auth_session):
        r = auth_session.get(f"{API}/dashboard", params={"tanggal": TODAY})
        assert r.status_code == 200
        assert r.json()["tanggal"] == TODAY

    def test_gender_sums_le_total_aktif(self, auth_session):
        b = auth_session.get(f"{API}/dashboard").json()
        assert b["gender"]["Laki-laki"] + b["gender"]["Perempuan"] <= b["total_aktif"]

    def test_perhatian_only_sakit_ijin_pulang(self, auth_session):
        b = auth_session.get(f"{API}/dashboard").json()
        for row in b["perhatian"]:
            assert row["Status"] in ("Sakit", "Ijin", "Pulang")
            for k in ("Nama", "Kelas", "Jenis_Kelamin", "Status", "Keterangan"):
                assert k in row

    def test_seeded_students_present_in_perhatian(self, auth_session):
        """Per agent context: Siti Nurhaliza(Sakit,demam), Budi Santoso(Ijin), Dewi Lestari(Pulang)."""
        b = auth_session.get(f"{API}/dashboard").json()
        by_name = {r["Nama"]: r for r in b["perhatian"]}
        # Soft-check presence (tolerate seed drift, but log)
        assert "Siti Nurhaliza" in by_name, f"perhatian={b['perhatian']}"
        assert by_name["Siti Nurhaliza"]["Status"] == "Sakit"
        assert "demam" in (by_name["Siti Nurhaliza"]["Keterangan"] or "").lower()
        assert "Budi Santoso" in by_name
        assert by_name["Budi Santoso"]["Status"] == "Ijin"
        assert "Dewi Lestari" in by_name
        assert by_name["Dewi Lestari"]["Status"] == "Pulang"

    def test_kehadiran_consistency(self, auth_session):
        """Hadir+Sakit+Ijin+Pulang == number of active students that have a row today."""
        b = auth_session.get(f"{API}/dashboard").json()
        tgl = b["tanggal"]  # Use dashboard's local (Asia/Jakarta) date
        s_active = auth_session.get(f"{API}/siswa", params={"status": "aktif"}).json()["data"]
        active_ids = {(s.get("ID_Siswa") or "").strip() for s in s_active}
        abs_today = auth_session.get(f"{API}/absensi", params={"tanggal": tgl}).json()["data"]
        active_rows = sum(1 for a in abs_today if (a.get("ID_Siswa") or "").strip() in active_ids)
        keh = b["kehadiran"]
        total = keh["Hadir"] + keh["Sakit"] + keh["Ijin"] + keh["Pulang"]
        assert total == active_rows, f"sum {total} != active_rows {active_rows} (kehadiran={keh})"

    def test_total_aktif_matches_siswa_aktif(self, auth_session):
        b = auth_session.get(f"{API}/dashboard").json()
        s_active = auth_session.get(f"{API}/siswa", params={"status": "aktif"}).json()
        assert b["total_aktif"] == s_active["count"]
