import { useEffect, useState, useMemo } from "react";
import axios, { API } from "../lib/api";
import { Spinner } from "../components/Spinner";
import { todayStr, prettyDate } from "../lib/format";

const DashboardPage = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [genderFilter, setGenderFilter] = useState("all");
  const [kelasFilter, setKelasFilter] = useState("all");
  const today = todayStr();

  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await axios.get(`${API}/dashboard`, {
          params: kelasFilter !== "all" ? { kelas: kelasFilter } : {},
        });
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
  }, [kelasFilter]);

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

      <div className="filter-bar" data-testid="dashboard-kelas-bar">
        <div className="field">
          <span className="label">Kelas</span>
          <select
            className="filter-select"
            value={kelasFilter}
            onChange={(e) => setKelasFilter(e.target.value)}
            data-testid="dashboard-filter-kelas"
          >
            <option value="all">Semua Kelas</option>
            {(data?.kelas_list || []).map((kk) => (
              <option key={kk} value={kk}>
                {kk}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading && <Spinner testid="dashboard-loading" />}
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
              <div className="table-scroll">
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
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
};

export default DashboardPage;
