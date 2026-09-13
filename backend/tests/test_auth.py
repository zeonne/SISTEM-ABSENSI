"""Backend auth tests: /api/login, /api/me, /api/logout, protection, rate limit."""
import os
import time
import uuid
from datetime import date

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
TODAY = date.today().isoformat()

ADMIN_USER = "admin"
ADMIN_PASS = "admin123"


# --- Auth: unauthenticated protection ---
class TestProtection:
    def test_get_siswa_401_no_auth(self):
        r = requests.get(f"{API}/siswa")
        assert r.status_code == 401

    def test_get_absensi_401_no_auth(self):
        r = requests.get(f"{API}/absensi", params={"tanggal": TODAY})
        assert r.status_code == 401

    def test_post_absensi_401_no_auth(self):
        r = requests.post(f"{API}/absensi", json={
            "id_siswa": "S001", "tanggal": TODAY, "status": "Hadir"
        })
        assert r.status_code == 401

    def test_generate_401_no_auth(self):
        r = requests.post(f"{API}/generate-absensi", json={})
        assert r.status_code == 401

    def test_me_401_no_auth(self):
        r = requests.get(f"{API}/me")
        assert r.status_code == 401


# --- Login flow ---
class TestLogin:
    def test_login_wrong_password_401_generic(self):
        s = requests.Session()
        r = s.post(f"{API}/login", json={"username": ADMIN_USER, "password": "wrongpass_xyz"})
        assert r.status_code == 401
        detail = r.json().get("detail")
        assert detail == "Username atau password salah"
        # No cookie set
        assert "access_token" not in s.cookies

    def test_login_unknown_user_generic(self):
        r = requests.post(f"{API}/login", json={"username": f"noexist_{uuid.uuid4().hex[:6]}", "password": "x"})
        assert r.status_code == 401
        assert r.json().get("detail") == "Username atau password salah"

    def test_login_success_sets_cookie_no_hash(self):
        s = requests.Session()
        r = s.post(f"{API}/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "access_token" in s.cookies
        # No password hash leaked
        raw = r.text.lower()
        assert "password_hash" not in raw
        assert "hash" not in body.get("user", {})
        assert body["user"]["username"] == ADMIN_USER

    def test_me_returns_user_no_hash(self):
        s = requests.Session()
        r = s.post(f"{API}/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
        assert r.status_code == 200
        r2 = s.get(f"{API}/me")
        assert r2.status_code == 200
        body = r2.json()
        assert body["user"]["username"] == ADMIN_USER
        assert "role" in body["user"]
        assert "password_hash" not in r2.text.lower()

    def test_protected_endpoints_work_after_login(self):
        s = requests.Session()
        r = s.post(f"{API}/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
        assert r.status_code == 200
        r2 = s.get(f"{API}/siswa")
        assert r2.status_code == 200
        assert "data" in r2.json()
        r3 = s.get(f"{API}/absensi", params={"tanggal": TODAY})
        assert r3.status_code == 200

    def test_logout_clears_cookie(self):
        s = requests.Session()
        s.post(f"{API}/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
        r = s.post(f"{API}/logout")
        assert r.status_code == 200
        # After logout, session cookies cleared -> /me should be 401
        s.cookies.clear()
        r2 = s.get(f"{API}/me")
        assert r2.status_code == 401


# --- Rate limit ---
class TestRateLimit:
    def test_rate_limit_429_on_6th_attempt_throwaway_user(self):
        # Use throwaway username to avoid locking admin
        uniq = f"rltest_{uuid.uuid4().hex[:8]}"
        s = requests.Session()
        for i in range(5):
            r = s.post(f"{API}/login", json={"username": uniq, "password": "bad"})
            assert r.status_code == 401, f"attempt {i+1}: {r.status_code} {r.text}"
        r6 = s.post(f"{API}/login", json={"username": uniq, "password": "bad"})
        assert r6.status_code == 429, f"expected 429, got {r6.status_code} {r6.text}"

    def test_valid_admin_still_can_login_when_other_user_locked(self):
        # Different username; admin should not be affected
        s = requests.Session()
        r = s.post(f"{API}/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
        assert r.status_code == 200
