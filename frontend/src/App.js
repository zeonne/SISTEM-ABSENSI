import { useEffect, useState, useCallback, useMemo } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster, toast } from "sonner";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const STATUS_OPTIONS = ["Hadir", "Sakit", "Ijin", "Pulang"];

const todayStr = () => new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD (local)

const fmtJam = (v) => {
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

const prettyDate = (d) => {
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

const Home = () => {
  const [config, setConfig] = useState(null);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [kelasFilter, setKelasFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");
  const today = todayStr();

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);

    const cfgPromise = axios
      .get(`${API}/config/sheets`)
      .then((res) => setConfig(res.data))
      .catch((e) => console.error("config error", e));

    const dataPromise = (async () => {
      try {
        const [siswaRes, absensiRes] = await Promise.all([
          axios.get(`${API}/siswa`),
          axios.get(`${API}/absensi`, { params: { tanggal: today } }),
        ]);
        const master = siswaRes.data.data || [];
        const absensi = absensiRes.data.data || [];
        const byId = {};
        absensi.forEach((a) => {
          byId[a.ID_Siswa] = a;
        });
        // Tanpa fallback: status diambil apa adanya dari Sheets.
        // Siswa tanpa baris hari ini = "belum diabsen" (bukan otomatis "Hadir").
        const merged = master.map((s) => {
          const a = byId[s.ID_Siswa];
          return {
            ID_Siswa: s.ID_Siswa,
            Nama: s.Nama,
            Kelas: s.Kelas,
            Status: a?.Status || "",
            Jam_Update: a?.Jam_Update || "",
            Keterangan: a?.Keterangan || "",
            hasRow: !!a,
            saving: false,
          };
        });
        setRows(merged);
      } catch (e) {
        const detail = e?.response?.data?.detail;
        setError(
          detail?.message ||
            "Tidak dapat mengambil data. Periksa koneksi backend."
        );
        setRows([]);
      }
    })();

    await Promise.all([cfgPromise, dataPromise]);
    setLoading(false);
  }, [today]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const generateToday = async () => {
    setGenerating(true);
    try {
      const res = await axios.post(`${API}/generate-absensi`, { tanggal: today });
      const d = res.data;
      toast.success(
        `Generate selesai: ${d.created} baris dibuat, ${d.skipped} sudah ada`
      );
      await loadData();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(detail?.message || "Gagal generate absensi");
    } finally {
      setGenerating(false);
    }
  };

  const saveRow = async (row, patch) => {
    const next = { ...row, ...patch };
    setRows((prev) =>
      prev.map((r) =>
        r.ID_Siswa === row.ID_Siswa ? { ...next, saving: true } : r
      )
    );
    try {
      const res = await axios.post(`${API}/absensi`, {
        id_siswa: next.ID_Siswa,
        tanggal: today,
        nama: next.Nama,
        kelas: next.Kelas,
        status: next.Status,
        keterangan: next.Keterangan,
      });
      const saved = res.data.row || {};
      setRows((prev) =>
        prev.map((r) =>
          r.ID_Siswa === row.ID_Siswa
            ? {
                ...next,
                Jam_Update: saved.Jam_Update || next.Jam_Update,
                hasRow: true,
                saving: false,
              }
            : r
        )
      );
      toast.success(`Status ${next.Nama} berhasil diperbarui → ${next.Status}`);
    } catch (e) {
      const detail = e?.response?.data?.detail;
      setRows((prev) =>
        prev.map((r) =>
          r.ID_Siswa === row.ID_Siswa ? { ...row, saving: false } : r
        )
      );
      toast.error(detail?.message || "Gagal menyimpan ke Google Sheets");
    }
  };

  const onStatusChange = (row, status) => {
    if (!status) return;
    const patch =
      status === "Hadir" ? { Status: status, Keterangan: "" } : { Status: status };
    saveRow(row, patch);
  };

  const onKeteranganInput = (id, val) => {
    setRows((prev) =>
      prev.map((r) => (r.ID_Siswa === id ? { ...r, Keterangan: val } : r))
    );
  };

  const onKeteranganBlur = (row) => {
    saveRow(row, { Keterangan: row.Keterangan });
  };

  const kelasList = useMemo(
    () => Array.from(new Set(rows.map((r) => r.Kelas).filter(Boolean))).sort(),
    [rows]
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((r) => {
      if (kelasFilter !== "all" && r.Kelas !== kelasFilter) return false;
      if (statusFilter !== "all" && r.Status !== statusFilter) return false;
      if (q && !(r.Nama || "").toLowerCase().includes(q)) return false;
      return true;
    });
  }, [rows, kelasFilter, statusFilter, search]);

  return (
    <div className="page" data-testid="home-page">
      <header className="page-header">
        <h1 className="title" data-testid="app-title">
          Sistem Absensi Sekolah
        </h1>
        <p className="subtitle">Pencatatan kehadiran siswa harian</p>
      </header>

      <section className="card" data-testid="absensi-card">
        <div className="card-header-row">
          <div>
            <h2 className="card-title">Absensi Hari Ini</h2>
            <p className="muted date-line" data-testid="today-date">
              {prettyDate(today)}
            </p>
          </div>
          <div className="header-actions">
            <button
              className="btn btn-secondary"
              onClick={generateToday}
              disabled={generating}
              data-testid="generate-button"
            >
              {generating ? "Memproses…" : "Generate Absensi"}
            </button>
            <button
              className="btn"
              onClick={loadData}
              data-testid="refresh-button"
            >
              Muat Ulang
            </button>
          </div>
        </div>

        {!loading && !error && rows.length > 0 && (
          <div className="filter-bar" data-testid="filter-bar">
            <div className="field">
              <span className="label">Kelas</span>
              <select
                className="filter-select"
                value={kelasFilter}
                onChange={(e) => setKelasFilter(e.target.value)}
                data-testid="filter-kelas"
              >
                <option value="all">Semua Kelas</option>
                {kelasList.map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <span className="label">Status</span>
              <select
                className="filter-select"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                data-testid="filter-status"
              >
                <option value="all">Semua Status</option>
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <div className="field field-grow">
              <span className="label">Cari Nama</span>
              <input
                className="search-input"
                type="text"
                placeholder="mis. Budi"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                data-testid="search-nama"
              />
            </div>
          </div>
        )}

        {loading && (
          <p className="muted" data-testid="loading">
            Memuat data…
          </p>
        )}

        {!loading && error && (
          <div className="alert" data-testid="error-message">
            <strong>Koneksi gagal:</strong> {error}
          </div>
        )}

        {!loading && !error && rows.length === 0 && (
          <p className="muted" data-testid="empty-message">
            Belum ada data siswa. Pastikan sheet Master_Siswa berisi data.
          </p>
        )}

        {!loading && !error && rows.length > 0 && filtered.length === 0 && (
          <p className="muted" data-testid="no-match-message">
            Tidak ada siswa yang cocok dengan filter.
          </p>
        )}

        {!loading && !error && filtered.length > 0 && (
          <table className="table" data-testid="absensi-table">
            <thead>
              <tr>
                <th>Nama</th>
                <th>Kelas</th>
                <th>Status</th>
                <th>Jam Update</th>
                <th>Keterangan</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr
                  key={r.ID_Siswa}
                  data-testid={`absensi-row-${r.ID_Siswa}`}
                  className={r.saving ? "saving" : ""}
                >
                  <td>{r.Nama}</td>
                  <td>{r.Kelas}</td>
                  <td>
                    <div className="status-cell">
                      <span
                        className={`badge badge-${(r.Status || "belum").toLowerCase()}`}
                        data-testid={`status-badge-${r.ID_Siswa}`}
                      >
                        {r.Status || "Belum"}
                      </span>
                      <select
                        className="status-select"
                        value={r.Status || ""}
                        disabled={r.saving}
                        onChange={(e) => onStatusChange(r, e.target.value)}
                        data-testid={`status-select-${r.ID_Siswa}`}
                      >
                        {!r.Status && (
                          <option value="" disabled>
                            Pilih…
                          </option>
                        )}
                        {STATUS_OPTIONS.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                    </div>
                  </td>
                  <td className="mono">{fmtJam(r.Jam_Update)}</td>
                  <td>
                    {r.Status && r.Status !== "Hadir" ? (
                      <input
                        className="ket-input"
                        type="text"
                        placeholder="Alasan (opsional)"
                        value={r.Keterangan}
                        disabled={r.saving}
                        onChange={(e) => onKeteranganInput(r.ID_Siswa, e.target.value)}
                        onBlur={() => onKeteranganBlur(r)}
                        data-testid={`keterangan-input-${r.ID_Siswa}`}
                      />
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {config && !config.spreadsheet_configured && (
        <section className="card" data-testid="config-card">
          <div className="alert">
            Google Sheets belum terkonfigurasi penuh. Email service account:{" "}
            <span className="mono">{config.service_account_email || "-"}</span>
          </div>
        </section>
      )}
    </div>
  );
};

function App() {
  return (
    <div className="App">
      <Toaster position="top-right" richColors />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
