import { useEffect, useState, useCallback, useMemo, createContext, useContext } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useNavigate, NavLink } from "react-router-dom";
import { Toaster, toast } from "sonner";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

axios.defaults.withCredentials = true;

const AuthContext = createContext(null);
const useAuth = () => useContext(AuthContext);

const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(undefined); // undefined=checking, null=guest, object=logged in

  useEffect(() => {
    const id = axios.interceptors.response.use(
      (r) => r,
      (error) => {
        if (error?.response?.status === 401) setUser(null);
        return Promise.reject(error);
      }
    );
    return () => axios.interceptors.response.eject(id);
  }, []);

  useEffect(() => {
    axios
      .get(`${API}/me`)
      .then((res) => setUser(res.data.user))
      .catch(() => setUser(null));
  }, []);

  const logout = async () => {
    try {
      await axios.post(`${API}/logout`);
    } catch (e) {
      /* ignore */
    }
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, setUser, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

const Login = () => {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (user) navigate("/", { replace: true });
  }, [user, navigate]);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setErr("");
    try {
      const res = await axios.post(`${API}/login`, { username, password });
      setUser(res.data.user);
      toast.success(`Selamat datang, ${res.data.user.nama || res.data.user.username}`);
      navigate("/", { replace: true });
    } catch (e2) {
      const d = e2?.response?.data?.detail;
      const msg = typeof d === "string" ? d : d?.message || "Gagal login. Coba lagi.";
      setErr(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit} data-testid="login-form">
        <h1 className="login-title">Sistem Absensi Sekolah</h1>
        <p className="login-sub">Masuk untuk melanjutkan</p>

        <label className="field-label">Username</label>
        <input
          className="login-input"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          data-testid="login-username"
          autoFocus
        />

        <label className="field-label">Password</label>
        <input
          className="login-input"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          data-testid="login-password"
        />

        {err && (
          <div className="alert" data-testid="login-error">
            {err}
          </div>
        )}

        <button
          className="btn login-btn"
          type="submit"
          disabled={submitting}
          data-testid="login-submit"
        >
          {submitting ? "Memproses…" : "Masuk"}
        </button>
      </form>
    </div>
  );
};

const Sidebar = () => {
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  const doLogout = async () => {
    await logout();
    toast.success("Berhasil logout");
    navigate("/login", { replace: true });
  };
  const linkClass = ({ isActive }) =>
    "nav-link" + (isActive ? " nav-link-active" : "");
  return (
    <aside className="sidebar" data-testid="sidebar">
      <div className="sidebar-brand">
        <span className="brand-mark">SA</span>
        <div>
          <div className="brand-title">Absensi Sekolah</div>
          <div className="brand-user">{user?.nama || user?.username}</div>
        </div>
      </div>
      <nav className="sidebar-nav">
        <NavLink to="/dashboard" className={linkClass} data-testid="nav-dashboard">
          Dashboard
        </NavLink>
        <NavLink to="/absensi" className={linkClass} data-testid="nav-absensi">
          Absensi
        </NavLink>
        <NavLink to="/siswa" className={linkClass} data-testid="nav-siswa">
          Siswa
        </NavLink>
        <span
          className="nav-link nav-link-disabled"
          data-testid="nav-sejarah"
          aria-disabled="true"
          title="Segera hadir"
        >
          Sejarah Aktivitas
        </span>
      </nav>
      <button className="nav-logout" onClick={doLogout} data-testid="nav-logout">
        Logout
      </button>
    </aside>
  );
};

const Layout = ({ children }) => (
  <div className="app-shell">
    <Sidebar />
    <main className="app-main">{children}</main>
  </div>
);

const ProtectedRoute = ({ children }) => {
  const { user } = useAuth();
  if (user === undefined)
    return (
      <div className="page">
        <p className="muted" data-testid="auth-checking">
          Memuat…
        </p>
      </div>
    );
  if (!user) return <Navigate to="/login" replace />;
  return <Layout>{children}</Layout>;
};

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
            Jenis_Kelamin: s.Jenis_Kelamin || "",
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

  const exportCSV = () => {
    const header = ["Nama", "Kelas", "Jenis Kelamin", "Status", "Jam Update", "Keterangan"];
    const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const lines = [header.map(esc).join(",")];
    filtered.forEach((r) => {
      lines.push(
        [r.Nama, r.Kelas, r.Jenis_Kelamin, r.Status || "Belum", fmtJam(r.Jam_Update), r.Keterangan]
          .map(esc)
          .join(",")
      );
    });
    const blob = new Blob(["\ufeff" + lines.join("\n")], {
      type: "text/csv;charset=utf-8;",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `rekap-absensi-${today}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Rekap absensi diunduh");
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
              onClick={exportCSV}
              disabled={filtered.length === 0}
              data-testid="export-button"
            >
              Ekspor Rekap
            </button>
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

const GENDER_OPTIONS = ["Laki-laki", "Perempuan"];

const SiswaPage = () => {
  const [tab, setTab] = useState("aktif");
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [kelasFilter, setKelasFilter] = useState("all");

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ nama: "", kelas: "", jenis_kelamin: "" });
  const [formErr, setFormErr] = useState("");
  const [saving, setSaving] = useState(false);

  const [confirmTarget, setConfirmTarget] = useState(null);
  const [confirmBusy, setConfirmBusy] = useState(false);

  const load = useCallback(async (which) => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get(`${API}/siswa`, { params: { status: which } });
      setList(res.data.data || []);
    } catch (e) {
      const d = e?.response?.data?.detail;
      setError(d?.message || "Gagal memuat data siswa.");
      setList([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(tab);
  }, [tab, load]);

  const kelasList = useMemo(
    () => Array.from(new Set(list.map((s) => s.Kelas).filter(Boolean))).sort(),
    [list]
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return list.filter((s) => {
      if (kelasFilter !== "all" && s.Kelas !== kelasFilter) return false;
      if (q && !(s.Nama || "").toLowerCase().includes(q)) return false;
      return true;
    });
  }, [list, search, kelasFilter]);

  const openAdd = () => {
    setEditing(null);
    setForm({ nama: "", kelas: "", jenis_kelamin: "" });
    setFormErr("");
    setModalOpen(true);
  };

  const openEdit = (s) => {
    setEditing(s);
    setForm({ nama: s.Nama || "", kelas: s.Kelas || "", jenis_kelamin: s.Jenis_Kelamin || "" });
    setFormErr("");
    setModalOpen(true);
  };

  const submitForm = async (e) => {
    e.preventDefault();
    if (!form.nama.trim()) return setFormErr("Nama tidak boleh kosong.");
    if (!form.kelas.trim()) return setFormErr("Kelas harus diisi.");
    if (!GENDER_OPTIONS.includes(form.jenis_kelamin))
      return setFormErr("Jenis Kelamin harus dipilih.");
    setSaving(true);
    setFormErr("");
    try {
      const body = {
        nama: form.nama.trim(),
        kelas: form.kelas.trim(),
        jenis_kelamin: form.jenis_kelamin,
      };
      if (editing) {
        await axios.put(`${API}/siswa/${editing.ID_Siswa}`, body);
        toast.success("Data siswa diperbarui");
      } else {
        await axios.post(`${API}/siswa`, body);
        toast.success("Siswa baru ditambahkan");
      }
      setModalOpen(false);
      await load(tab);
    } catch (e2) {
      const d = e2?.response?.data?.detail;
      setFormErr(typeof d === "string" ? d : d?.message || "Gagal menyimpan.");
    } finally {
      setSaving(false);
    }
  };

  const doNonaktif = async () => {
    if (!confirmTarget) return;
    setConfirmBusy(true);
    try {
      await axios.post(`${API}/siswa/${confirmTarget.ID_Siswa}/status`, {
        status_aktif: "Nonaktif",
      });
      toast.success(`${confirmTarget.Nama} dinonaktifkan`);
      setConfirmTarget(null);
      await load(tab);
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(d?.message || "Gagal menonaktifkan siswa");
    } finally {
      setConfirmBusy(false);
    }
  };

  const doAktifkan = async (s) => {
    try {
      await axios.post(`${API}/siswa/${s.ID_Siswa}/status`, { status_aktif: "Aktif" });
      toast.success(`${s.Nama} diaktifkan kembali`);
      await load(tab);
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(d?.message || "Gagal mengaktifkan siswa");
    }
  };

  return (
    <div className="page" data-testid="siswa-page">
      <header className="page-header">
        <h1 className="title">Data Siswa</h1>
        <p className="subtitle">Kelola daftar siswa (Master_Siswa)</p>
      </header>

      <section className="card">
        <div className="card-header-row">
          <div className="tabs">
            <button
              className={"tab" + (tab === "aktif" ? " tab-active" : "")}
              onClick={() => setTab("aktif")}
              data-testid="tab-aktif"
            >
              Aktif
            </button>
            <button
              className={"tab" + (tab === "nonaktif" ? " tab-active" : "")}
              onClick={() => setTab("nonaktif")}
              data-testid="tab-nonaktif"
            >
              Nonaktif
            </button>
          </div>
          {tab === "aktif" && (
            <button className="btn" onClick={openAdd} data-testid="add-siswa-button">
              + Tambah Siswa
            </button>
          )}
        </div>

        <div className="filter-bar">
          <div className="field">
            <span className="label">Kelas</span>
            <select
              className="filter-select"
              value={kelasFilter}
              onChange={(e) => setKelasFilter(e.target.value)}
              data-testid="siswa-filter-kelas"
            >
              <option value="all">Semua Kelas</option>
              {kelasList.map((k) => (
                <option key={k} value={k}>
                  {k}
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
              data-testid="siswa-search"
            />
          </div>
        </div>

        {loading && <p className="muted" data-testid="siswa-loading">Memuat data…</p>}

        {!loading && error && (
          <div className="alert" data-testid="siswa-error">
            {error}
          </div>
        )}

        {!loading && !error && filtered.length === 0 && (
          <p className="muted" data-testid="siswa-empty">
            {tab === "nonaktif"
              ? "Tidak ada siswa nonaktif."
              : "Belum ada siswa. Klik “Tambah Siswa” untuk menambah."}
          </p>
        )}

        {!loading && !error && filtered.length > 0 && (
          <table className="table" data-testid="siswa-table">
            <thead>
              <tr>
                <th>Nama</th>
                <th>Kelas</th>
                <th>Jenis Kelamin</th>
                <th>Aksi</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => (
                <tr key={s.ID_Siswa} data-testid={`siswa-row-${s.ID_Siswa}`}>
                  <td>{s.Nama}</td>
                  <td>{s.Kelas}</td>
                  <td>{s.Jenis_Kelamin}</td>
                  <td>
                    {tab === "aktif" ? (
                      <div className="row-actions">
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => openEdit(s)}
                          data-testid={`edit-siswa-${s.ID_Siswa}`}
                        >
                          Edit
                        </button>
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => setConfirmTarget(s)}
                          data-testid={`nonaktif-siswa-${s.ID_Siswa}`}
                        >
                          Nonaktifkan
                        </button>
                      </div>
                    ) : (
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => doAktifkan(s)}
                        data-testid={`aktifkan-siswa-${s.ID_Siswa}`}
                      >
                        Aktifkan
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {modalOpen && (
        <div className="modal-overlay" data-testid="siswa-modal">
          <form className="modal-card" onSubmit={submitForm} data-testid="siswa-form">
            <h2 className="card-title">
              {editing ? "Edit Siswa" : "Tambah Siswa"}
            </h2>

            <label className="field-label">Nama</label>
            <input
              className="login-input"
              value={form.nama}
              onChange={(e) => setForm({ ...form, nama: e.target.value })}
              data-testid="form-nama"
              autoFocus
            />

            <label className="field-label">Kelas</label>
            <input
              className="login-input"
              value={form.kelas}
              placeholder="mis. 6A"
              onChange={(e) => setForm({ ...form, kelas: e.target.value })}
              data-testid="form-kelas"
            />

            <label className="field-label">Jenis Kelamin</label>
            <select
              className="login-input"
              value={form.jenis_kelamin}
              onChange={(e) => setForm({ ...form, jenis_kelamin: e.target.value })}
              data-testid="form-jenis-kelamin"
            >
              <option value="">— Pilih —</option>
              {GENDER_OPTIONS.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>

            {formErr && (
              <div className="alert" data-testid="form-error">
                {formErr}
              </div>
            )}

            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setModalOpen(false)}
                data-testid="form-cancel"
              >
                Batal
              </button>
              <button
                type="submit"
                className="btn"
                disabled={saving}
                data-testid="form-submit"
              >
                {saving ? "Menyimpan…" : "Simpan"}
              </button>
            </div>
          </form>
        </div>
      )}

      {confirmTarget && (
        <div className="modal-overlay" data-testid="confirm-dialog">
          <div className="modal-card confirm-card">
            <h2 className="card-title">Nonaktifkan Siswa</h2>
            <p className="muted">
              Yakin ingin menonaktifkan <strong>{confirmTarget.Nama}</strong>? Data
              absensinya tetap tersimpan; siswa hanya disembunyikan dari daftar aktif.
            </p>
            <div className="modal-actions">
              <button
                className="btn btn-secondary"
                onClick={() => setConfirmTarget(null)}
                data-testid="confirm-no"
              >
                Batal
              </button>
              <button
                className="btn btn-danger"
                onClick={doNonaktif}
                disabled={confirmBusy}
                data-testid="confirm-yes"
              >
                {confirmBusy ? "Memproses…" : "Ya, Nonaktifkan"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const DashboardPage = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [genderFilter, setGenderFilter] = useState("all");
  const today = todayStr();

  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await axios.get(`${API}/dashboard`);
        if (active) setData(res.data);
      } catch (e) {
        const d = e?.response?.data?.detail;
        if (active) setError(d?.message || "Gagal memuat dashboard.");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [today]);

  const list = data?.perhatian || [];
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return list.filter((s) => {
      if (genderFilter !== "all" && s.Jenis_Kelamin !== genderFilter) return false;
      if (q && !(s.Nama || "").toLowerCase().includes(q)) return false;
      return true;
    });
  }, [list, search, genderFilter]);

  const k = data?.kehadiran || {};
  const g = data?.gender || {};

  return (
    <div className="page" data-testid="dashboard-page">
      <header className="page-header">
        <h1 className="title">Dashboard</h1>
        <p className="subtitle date-line">{prettyDate(data?.tanggal || today)}</p>
      </header>

      {loading && <p className="muted" data-testid="dashboard-loading">Memuat data…</p>}
      {!loading && error && (
        <div className="alert" data-testid="dashboard-error">{error}</div>
      )}

      {!loading && !error && data && (
        <>
          <div className="stat-grid" data-testid="stat-kehadiran">
            <div className="stat-card stat-hadir" data-testid="stat-hadir">
              <span className="stat-num">{k.Hadir || 0}</span>
              <span className="stat-label">Hadir</span>
            </div>
            <div className="stat-card stat-sakit" data-testid="stat-sakit">
              <span className="stat-num">{k.Sakit || 0}</span>
              <span className="stat-label">Sakit</span>
            </div>
            <div className="stat-card stat-ijin" data-testid="stat-ijin">
              <span className="stat-num">{k.Ijin || 0}</span>
              <span className="stat-label">Ijin</span>
            </div>
            <div className="stat-card stat-pulang" data-testid="stat-pulang">
              <span className="stat-num">{k.Pulang || 0}</span>
              <span className="stat-label">Pulang</span>
            </div>
          </div>

          <div className="stat-grid stat-grid-2" data-testid="stat-gender">
            <div className="stat-card stat-lk" data-testid="stat-laki">
              <span className="stat-num">{g["Laki-laki"] || 0}</span>
              <span className="stat-label">Siswa Laki-laki (aktif)</span>
            </div>
            <div className="stat-card stat-pr" data-testid="stat-perempuan">
              <span className="stat-num">{g["Perempuan"] || 0}</span>
              <span className="stat-label">Siswa Perempuan (aktif)</span>
            </div>
          </div>

          <section className="card">
            <h2 className="card-title">Siswa Tidak Hadir Penuh Hari Ini (Sakit / Ijin / Pulang)</h2>
            <div className="filter-bar">
              <div className="field">
                <span className="label">Jenis Kelamin</span>
                <select
                  className="filter-select"
                  value={genderFilter}
                  onChange={(e) => setGenderFilter(e.target.value)}
                  data-testid="dashboard-filter-gender"
                >
                  <option value="all">Semua</option>
                  <option value="Laki-laki">Laki-laki</option>
                  <option value="Perempuan">Perempuan</option>
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
                  data-testid="dashboard-search"
                />
              </div>
            </div>

            {filtered.length === 0 ? (
              <p className="muted" data-testid="dashboard-perhatian-empty">
                Tidak ada siswa Sakit/Ijin/Pulang yang cocok.
              </p>
            ) : (
              <table className="table" data-testid="dashboard-perhatian-table">
                <thead>
                  <tr>
                    <th>Nama</th>
                    <th>Kelas</th>
                    <th>Jenis Kelamin</th>
                    <th>Status</th>
                    <th>Keterangan</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((s, i) => (
                    <tr key={`${s.Nama}-${i}`} data-testid={`dashboard-row-${i}`}>
                      <td>{s.Nama}</td>
                      <td>{s.Kelas}</td>
                      <td>{s.Jenis_Kelamin}</td>
                      <td>
                        <span className={`badge badge-${(s.Status || "").toLowerCase()}`}>
                          {s.Status}
                        </span>
                      </td>
                      <td>{s.Keterangan || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </div>
  );
};

function App() {
  return (
    <div className="App">
      <Toaster position="top-right" richColors />
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/absensi"
              element={
                <ProtectedRoute>
                  <Home />
                </ProtectedRoute>
              }
            />
            <Route
              path="/siswa"
              element={
                <ProtectedRoute>
                  <SiswaPage />
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
