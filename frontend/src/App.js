import { useEffect, useState, useCallback } from "react";
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
        // Fallback: siswa tanpa baris absensi hari ini dianggap "Hadir".
        const merged = master.map((s) => {
          const a = byId[s.ID_Siswa];
          return {
            ID_Siswa: s.ID_Siswa,
            Nama: s.Nama,
            Kelas: s.Kelas,
            Status: a?.Status || "Hadir",
            Jam_Update: a?.Jam_Update || "",
            Keterangan: a?.Keterangan || "",
            saved: !!a,
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

  const saveRow = async (idx, patch) => {
    const current = rows[idx];
    const next = { ...current, ...patch };
    setRows((prev) =>
      prev.map((r, i) => (i === idx ? { ...next, saving: true } : r))
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
        prev.map((r, i) =>
          i === idx
            ? {
                ...next,
                Jam_Update: saved.Jam_Update || next.Jam_Update,
                saved: true,
                saving: false,
              }
            : r
        )
      );
      toast.success(`Status ${next.Nama} berhasil diperbarui → ${next.Status}`);
    } catch (e) {
      const detail = e?.response?.data?.detail;
      setRows((prev) =>
        prev.map((r, i) => (i === idx ? { ...current, saving: false } : r))
      );
      toast.error(detail?.message || "Gagal menyimpan ke Google Sheets");
    }
  };

  const onStatusChange = (idx, status) => {
    const patch =
      status === "Hadir" ? { Status: status, Keterangan: "" } : { Status: status };
    saveRow(idx, patch);
  };

  const onKeteranganInput = (idx, val) => {
    setRows((prev) =>
      prev.map((r, i) => (i === idx ? { ...r, Keterangan: val } : r))
    );
  };

  const onKeteranganBlur = (idx) => {
    saveRow(idx, { Keterangan: rows[idx].Keterangan });
  };

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
          <button className="btn" onClick={loadData} data-testid="refresh-button">
            Muat Ulang
          </button>
        </div>

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

        {!loading && !error && rows.length > 0 && (
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
              {rows.map((r, i) => (
                <tr
                  key={r.ID_Siswa || i}
                  data-testid={`absensi-row-${r.ID_Siswa}`}
                  className={r.saving ? "saving" : ""}
                >
                  <td>{r.Nama}</td>
                  <td>{r.Kelas}</td>
                  <td>
                    <div className="status-cell">
                      <span
                        className={`badge badge-${r.Status.toLowerCase()}`}
                        data-testid={`status-badge-${r.ID_Siswa}`}
                      >
                        {r.Status}
                      </span>
                      <select
                        className="status-select"
                        value={r.Status}
                        disabled={r.saving}
                        onChange={(e) => onStatusChange(i, e.target.value)}
                        data-testid={`status-select-${r.ID_Siswa}`}
                      >
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
                    {r.Status !== "Hadir" ? (
                      <input
                        className="ket-input"
                        type="text"
                        placeholder="Alasan (opsional)"
                        value={r.Keterangan}
                        disabled={r.saving}
                        onChange={(e) => onKeteranganInput(i, e.target.value)}
                        onBlur={() => onKeteranganBlur(i)}
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
