import { useEffect, useState, useCallback, useMemo } from "react";
import { toast } from "sonner";
import axios, { API } from "../lib/api";
import { Pagination } from "../components/Pagination";
import { Spinner } from "../components/Spinner";
import { GENDER_OPTIONS } from "../lib/format";

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

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  useEffect(() => {
    setPage(1);
  }, [search, kelasFilter, tab]);
  const paged = useMemo(
    () => filtered.slice((page - 1) * pageSize, page * pageSize),
    [filtered, page, pageSize]
  );

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

        {loading && <Spinner testid="siswa-loading" />}

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
          <div className="table-scroll">
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
                {paged.map((s) => (
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
          </div>
        )}
        {!loading && !error && filtered.length > 0 && (
          <Pagination
            total={filtered.length}
            page={page}
            pageSize={pageSize}
            onPage={setPage}
            onSize={(n) => {
              setPageSize(n);
              setPage(1);
            }}
            testid="siswa-pagination"
          />
        )}
      </section>

      {modalOpen && (
        <div className="modal-overlay" data-testid="siswa-modal">
          <form className="modal-card" onSubmit={submitForm} data-testid="siswa-form">
            <h2 className="card-title">{editing ? "Edit Siswa" : "Tambah Siswa"}</h2>

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

export default SiswaPage;
