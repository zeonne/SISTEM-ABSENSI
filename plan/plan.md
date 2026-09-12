# Rencana: Fondasi Web App Sistem Absensi Sekolah (Tahap 1)

## Tujuan tahap ini
Membuat kerangka dasar (skeleton) aplikasi absensi sekolah. Belum ada koneksi Google Sheets, belum ada fitur ubah status, belum ada tabel data, belum ada logic absensi. Semua itu akan diminta di prompt terpisah berikutnya.

## Yang akan dibuat

### 1. Halaman utama (frontend)
- Halaman tunggal berisi:
  - Judul besar: **"Sistem Absensi Sekolah"**
  - Subjudul singkat (bahasa campuran Indonesia/Inggris) yang menjelaskan aplikasi.
- Tampilan bersih dan rapi, tanpa fungsi/tombol yang bekerja.
- Data dummy siswa TIDAK ditampilkan di halaman (sesuai pilihan), hanya disiapkan di sisi kode/backend sebagai referensi struktur.

### 2. Backend dasar (placeholder / kosongan)
- Struktur backend disiapkan sebagai kerangka, siap dihubungkan ke Google Sheets nanti.
- Menyediakan endpoint placeholder sederhana yang hanya mengembalikan status "aktif" dan data dummy referensi (tanpa logic absensi apa pun).
- Belum ada koneksi ke Google Sheets API.

### 3. Data dummy referensi (struktur Google Sheets)
Disiapkan mengikuti struktur yang diminta, sebagai acuan untuk tahap berikutnya:

**Master_Siswa** (5 siswa dummy, semua kelas "XII"):
- ID_Siswa, Nama, Kelas
- Contoh: 5 siswa dengan nama dummy, kelas = "XII"

**Absensi** (struktur kolom saja, belum ada data):
- Tanggal, ID_Siswa, Nama, Kelas, Status (default "Hadir"), Jam_Update, Keterangan

### 4. Placeholder status kehadiran
- 4 kategori status disiapkan sebagai konstanta di kode: **Hadir** (default), **Sakit**, **Ijin**, **Pulang**.
- Hanya sebagai definisi/placeholder — belum ada logic atau tombol yang menggunakannya.

## Yang TIDAK dibuat di tahap ini (sesuai permintaan)
- Koneksi ke Google Sheets API
- Fitur ubah status kehadiran
- Tampilan tabel data siswa/absensi
- Logic absensi apa pun

## Catatan / asumsi
- Halaman utama menampilkan judul + subjudul saja (bukan minimal judul saja), sesuai pilihan.
- Kelas untuk 5 siswa dummy = "XII".
- Bahasa antarmuka: campuran Indonesia/Inggris.
- Nama-nama siswa dummy akan dipilihkan (nama umum Indonesia) karena tidak ada preferensi khusus.

## Langkah berikutnya (di luar tahap ini)
Setelah fondasi ini disetujui dan jadi, tahap berikutnya (prompt terpisah): menghubungkan backend ke Google Sheets, menampilkan tabel data, dan menambahkan fitur ubah status absensi.
