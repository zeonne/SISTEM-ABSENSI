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
- P2: Halaman Sejarah Aktivitas (placeholder nav sudah ada)

### Tahap 8 — Dashboard (2026-06)
- Urutan sidebar: **Dashboard, Absensi, Siswa, Sejarah Aktivitas** (placeholder); Logout tetap di bawah
- **Dashboard** jadi halaman default setelah login (`/` → `/dashboard`), read-only
- `GET /api/dashboard` (agregasi ringan di backend, hanya siswa Aktif): kartu Hadir/Sakit/Ijin/Pulang hari ini, jumlah siswa per jenis kelamin, dan daftar siswa Sakit/Ijin/Pulang
- Search nama + filter jenis kelamin (bisa digabung) pada tabel perhatian
- Dashboard memakai tanggal default backend (Asia/Jakarta) agar tidak drift dengan timezone browser
- Testing agent: backend 100% (8/8), frontend 100% (fix minor timezone diterapkan)

### Tahap 7 — Navigasi + CRUD Siswa (2026-06)
- **Sidebar** di semua halaman setelah login: Absensi, Siswa, Dashboard (nonaktif), Sejarah Aktivitas (nonaktif), Logout (di bawah); logout dipindah dari header Absensi
- Halaman **Siswa** (`/siswa`): daftar siswa aktif (Nama/Kelas/Jenis Kelamin) + search nama & filter kelas; tab Aktif/Nonaktif
- Tambah siswa: auto ID `S###` unik, log "Tambah Siswa"; Edit: log "Edit Siswa" + detail perubahan; validasi (Nama/Kelas/Jenis Kelamin wajib)
- **Soft delete**: kolom `Status_Aktif` (Aktif/Nonaktif) di Master_Siswa; "hapus" = set Nonaktif (dialog konfirmasi), riwayat Absensi tetap utuh; log "Nonaktifkan Siswa" / "Aktifkan Siswa"
- `read_master_siswa`/`GET /api/siswa` default hanya Aktif (`?status=nonaktif|all`); generate absensi & halaman Absensi mengabaikan siswa nonaktif
- Endpoint baru diproteksi login. Testing agent: backend 100% (14/14), frontend 100%

### Tahap 6 — Autentikasi (2026-06)
- Halaman **Login** terpisah (Username/Password); route `/` diproteksi `ProtectedRoute`, `/login` publik
- `POST /api/login`: cocokkan ke sheet Users via **bcrypt** (verify_password), pesan gagal generik "Username atau password salah"; sukses → JWT httpOnly cookie, update Terakhir_Login, log "Login"
- `GET /api/me`, `POST /api/logout` (log "Logout"); tombol Logout di halaman utama
- Semua endpoint lama (siswa, absensi GET/POST, generate) diproteksi `Depends(get_current_user)` → 401 tanpa token
- **Rate limiting** login gagal: 5x → 429 (window 15 mnt, key X-Forwarded-For + username; per-user, admin tak terkunci)
- Password_Hash tidak pernah dikirim ke frontend; JWT_SECRET di .env; cookie secure+lax (same-origin)
- Testing agent: backend 100% (13/13), frontend 100%

### Tahap 5 — Persiapan Struktur (2026-06)
- Master_Siswa: kolom `Jenis_Kelamin` ditambah (dummy Laki-laki/Perempuan bergantian); `GET /api/siswa` ikut mengembalikannya
- Sheet baru **Users** (ID_User, Nama, Username, Password_Hash, Role, Terakhir_Login) + admin default (`admin`/`admin123`, role admin) — password **bcrypt** ($2b$), seeding idempoten saat startup
- Sheet baru **Log_Aktivitas** (Timestamp, User, Aksi, Detail) + `append_log()`; dipanggil setiap ubah status absensi (Aksi="Ubah Status Absensi", Detail="Nama → Status")
- Fungsi READ/WRITE Users (`read_users`, `write_user` upsert by Username), `hash_password`/`verify_password`
- `ensure_structure()` idempoten membuat tab & kolom saat startup (tidak merusak fitur lama)
- Frontend: tombol **Ekspor Rekap** (unduh CSV absensi hari itu, mengikuti filter aktif); Jenis_Kelamin ikut di CSV
- `.env`: `ADMIN_USERNAME`, `ADMIN_PASSWORD`
- Verifikasi langsung: 4 tab ada, admin bcrypt verify=True, log tertulis, semua idempoten

### Tahap 4 — Generate Otomatis + Filter (2026-06)
- `generate_absensi_for_date(tanggal)`: append baris "Hadir" hanya untuk siswa yang BELUM punya baris di tanggal itu (idempoten, tidak menimpa edit guru), atomik dalam satu `_SHEETS_LOCK`
- `POST /api/generate-absensi` (trigger manual/testing, default hari ini WIB)
- Cron platform `.emergent/crons.yml`: `generate-absensi` tiap 06:00 Asia/Jakarta → `POST /api/cron/generate-absensi`
- Webhook cron diamankan Bearer `WEBHOOK_CRON_SECRET` (hmac.compare_digest, ack 2xx + kerja via BackgroundTasks); `.env` tambah `APP_TIMEZONE`, `WEBHOOK_CRON_SECRET`
- Frontend: fallback "Hadir" palsu DIHAPUS (siswa tanpa baris → badge "Belum"); tombol "Generate Absensi"
- Filter client-side: dropdown Kelas (unik + Semua), dropdown Status (Semua/Hadir/Sakit/Ijin/Pulang), search nama (case-insensitive, substring) — ketiganya kombinasikan
- Testing agent: backend 100%, frontend 100%. Diverifikasi: generate idempoten (created=0 saat ulang), edit guru tidak tertimpa, tanpa duplikat, cron 401/401/200
