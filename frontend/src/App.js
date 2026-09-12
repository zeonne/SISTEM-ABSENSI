import { useEffect, useState, useCallback } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Home = () => {
  const [config, setConfig] = useState(null);
  const [siswa, setSiswa] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);

    const cfgPromise = axios
      .get(`${API}/config/sheets`)
      .then((res) => setConfig(res.data))
      .catch((e) => console.error("config error", e));

    const siswaPromise = axios
      .get(`${API}/siswa`)
      .then((res) => setSiswa(res.data.data || []))
      .catch((e) => {
        const detail = e?.response?.data?.detail;
        setError(
          detail?.message ||
            "Tidak dapat mengambil data siswa. Periksa koneksi backend."
        );
        setSiswa([]);
      });

    await Promise.all([cfgPromise, siswaPromise]);
    setLoading(false);
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  return (
    <div className="page" data-testid="home-page">
      <header className="page-header">
        <h1 className="title" data-testid="app-title">
          Sistem Absensi Sekolah
        </h1>
        <p className="subtitle">Pencatatan kehadiran siswa harian</p>
      </header>

      <section className="card" data-testid="config-card">
        <h2 className="card-title">Status Koneksi Google Sheets</h2>
        {config ? (
          <div className="config-grid" data-testid="config-status">
            <div>
              <span className="label">Service Account</span>
              <span className={config.service_account_configured ? "ok" : "warn"}>
                {config.service_account_configured ? "Terkonfigurasi" : "Belum diunggah"}
              </span>
            </div>
            <div>
              <span className="label">Email Service Account</span>
              <span className="mono" data-testid="service-account-email">
                {config.service_account_email || "-"}
              </span>
            </div>
            <div>
              <span className="label">Spreadsheet ID</span>
              <span className={config.spreadsheet_configured ? "ok" : "warn"}>
                {config.spreadsheet_configured ? "Terkonfigurasi" : "Belum diatur"}
              </span>
            </div>
          </div>
        ) : (
          <p className="muted">Memuat status konfigurasi…</p>
        )}
      </section>

      <section className="card" data-testid="siswa-card">
        <div className="card-header-row">
          <h2 className="card-title">Data Siswa (Master_Siswa)</h2>
          <button className="btn" onClick={loadData} data-testid="refresh-button">
            Muat Ulang
          </button>
        </div>

        {loading && <p className="muted" data-testid="loading">Memuat data…</p>}

        {!loading && error && (
          <div className="alert" data-testid="error-message">
            <strong>Koneksi gagal:</strong> {error}
          </div>
        )}

        {!loading && !error && siswa.length === 0 && (
          <p className="muted" data-testid="empty-message">
            Belum ada data. Pastikan spreadsheet sudah di-share dan berisi data.
          </p>
        )}

        {!loading && !error && siswa.length > 0 && (
          <table className="table" data-testid="siswa-table">
            <thead>
              <tr>
                <th>ID_Siswa</th>
                <th>Nama</th>
                <th>Kelas</th>
              </tr>
            </thead>
            <tbody>
              {siswa.map((s, i) => (
                <tr key={s.ID_Siswa || i} data-testid={`siswa-row-${i}`}>
                  <td className="mono">{s.ID_Siswa}</td>
                  <td>{s.Nama}</td>
                  <td>{s.Kelas}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
};

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
