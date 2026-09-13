# PRD — Sistem Absensi Sekolah

## Problem Statement
Web app absensi sekolah sederhana untuk guru/wali kelas, memakai **Google Sheets sebagai database**.
Status kehadiran harian: Hadir (default), Sakit, Ijin, Pulang.

## Arsitektur
- Frontend: React (halaman utama + tabel siswa)
- Backend: FastAPI (`/api` prefix)
- Database: **Google Sheets** via **service account** (non-interactive)
- MongoDB tersedia (belum dipakai untuk data absensi)

### Struktur Google Sheets (spreadsheet "SISTEM_ABSENSI")
- `Master_Siswa`: ID_Siswa, Nama, Kelas
- `Absensi`: Tanggal, ID_Siswa, Nama, Kelas, Status, Jam_Update, Keterangan

### Konfigurasi (backend/.env)
- `GOOGLE_SERVICE_ACCOUNT_FILE=/app/backend/service_account.json`
- `GOOGLE_SPREADSHEET_ID=1GoXxhEDx82VkjDg1vFwriCf_vKNAOJ0XDFKq-YmaT14`
- Email service account: `absensi-bot@exalted-ability-508523-a4.iam.gserviceaccount.com` (di-share sebagai Editor)

## User Persona
- Guru / wali kelas: mencatat & meninjau kehadiran siswa harian.

## Sudah Diimplementasikan
### Tahap 1 — Fondasi (2026-06)
- Skeleton frontend: halaman "Sistem Absensi Sekolah"
- Backend placeholder + data dummy referensi (`sample_master_siswa.json`)

### Tahap 2 — Koneksi Google Sheets (2026-06)
- `backend/sheets_service.py`: koneksi service account (cached client, static discovery), error handling informatif (`SheetsError` + mapping 403/404/400)
- Fungsi READ: `read_master_siswa()`, `read_absensi(tanggal)`
- Fungsi WRITE: `write_absensi_row(id_siswa, tanggal, ...)` — update in-place by (ID_Siswa, Tanggal), else append; set Jam_Update
- Endpoint nyata: `GET /api/siswa`, `GET /api/absensi?tanggal=`, `GET /api/config/sheets`
- Blocking Google calls dijalankan via `asyncio.to_thread` (tidak memblok event loop)
- Frontend menampilkan status koneksi + tabel Master_Siswa (verified: 5 siswa tampil)
- Seed 5 siswa dummy + header Absensi ke spreadsheet nyata

### Tahap 3 — Fitur Inti Absensi (2026-06)
- Endpoint `POST /api/absensi` (upsert by ID_Siswa+Tanggal, validasi status 422, error handling)
- Halaman utama: tabel Absensi Hari Ini (Nama, Kelas, Status, Jam_Update, Keterangan)
- Fallback frontend: siswa tanpa baris hari ini tampil default "Hadir"
- Dropdown ubah status (Hadir/Sakit/Ijin/Pulang) → simpan ke Sheets + toast, tanpa reload
- Keterangan opsional muncul untuk status non-Hadir, ikut tersimpan
- Badge warna per status (Hadir hijau, Sakit merah, Ijin biru, Pulang ungu)
- FIX kritikal: `threading.Lock` pada semua panggilan Sheets (httplib2 tidak thread-safe → sebelumnya crash/hang saat request paralel)
- FIX: read+write atomik dalam satu lock → tidak ada duplikat baris untuk key sama meski request bersamaan (diverifikasi 5 write paralel → 1 baris)
- Testing agent: backend 100%, frontend 100%

## Backlog (belum dikerjakan — sesuai permintaan)
- P2: Rekap/riwayat tanggal sebelumnya (pemilih tanggal)
- P2: Dashboard statistik
- P2: CRUD siswa, login/logout (di luar cakupan saat ini)

### Tahap 4 — Generate Otomatis + Filter (2026-06)
- `generate_absensi_for_date(tanggal)`: append baris "Hadir" hanya untuk siswa yang BELUM punya baris di tanggal itu (idempoten, tidak menimpa edit guru), atomik dalam satu `_SHEETS_LOCK`
- `POST /api/generate-absensi` (trigger manual/testing, default hari ini WIB)
- Cron platform `.emergent/crons.yml`: `generate-absensi` tiap 06:00 Asia/Jakarta → `POST /api/cron/generate-absensi`
- Webhook cron diamankan Bearer `WEBHOOK_CRON_SECRET` (hmac.compare_digest, ack 2xx + kerja via BackgroundTasks); `.env` tambah `APP_TIMEZONE`, `WEBHOOK_CRON_SECRET`
- Frontend: fallback "Hadir" palsu DIHAPUS (siswa tanpa baris → badge "Belum"); tombol "Generate Absensi"
- Filter client-side: dropdown Kelas (unik + Semua), dropdown Status (Semua/Hadir/Sakit/Ijin/Pulang), search nama (case-insensitive, substring) — ketiganya kombinasikan
- Testing agent: backend 100%, frontend 100%. Diverifikasi: generate idempoten (created=0 saat ulang), edit guru tidak tertimpa, tanpa duplikat, cron 401/401/200
