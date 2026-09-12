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

## Backlog (belum dikerjakan — sesuai permintaan)
- P0: Fitur ubah status kehadiran (Hadir/Sakit/Ijin/Pulang) via UI → WRITE endpoint
- P1: Generate absensi otomatis harian (default Hadir untuk semua siswa)
- P1: Filter per kelas
- P2: Rekap/laporan, tampilan tabel absensi harian
- P2: Rotasi/pengamanan key service account untuk produksi
