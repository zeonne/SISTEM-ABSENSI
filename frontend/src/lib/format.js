export const STATUS_OPTIONS = ["Hadir", "Sakit", "Ijin", "Pulang"];
export const GENDER_OPTIONS = ["Laki-laki", "Perempuan"];
export const PAGE_SIZES = [5, 10, 50, 100];

export const AKSI_OPTIONS = [
  "Login",
  "Logout",
  "Ubah Status Absensi",
  "Tambah Siswa",
  "Edit Siswa",
  "Nonaktifkan Siswa",
  "Aktifkan Siswa",
];

export const todayStr = () => new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD (local)

export const fmtJam = (v) => {
  if (!v) return "—";
  try {
    return new Date(v).toLocaleTimeString("id-ID", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return v;
  }
};

export const prettyDate = (d) => {
  try {
    return new Date(d + "T00:00:00").toLocaleDateString("id-ID", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  } catch {
    return d;
  }
};

export const fmtWaktu = (v) => {
  if (!v) return "—";
  try {
    return new Date(v).toLocaleString("id-ID", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return v;
  }
};
