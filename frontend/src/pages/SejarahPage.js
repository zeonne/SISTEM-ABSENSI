import { useEffect, useState, useMemo } from "react";
import axios, { API } from "../lib/api";
import { Pagination } from "../components/Pagination";
import { Spinner } from "../components/Spinner";
import { AKSI_OPTIONS, fmtWaktu } from "../lib/format";

const SejarahPage = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [aksiFilter, setAksiFilter] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await axios.get(`${API}/logs`);
        setLogs(res.data.data || []);
      } catch (e) {
        const d = e?.response?.data?.detail;
        setError(d?.message || "Gagal memuat log.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const filtered = useMemo(() => {
    const rows = [...logs].sort((a, b) =>
      (b.Timestamp || "").localeCompare(a.Timestamp || "")
    );
    return rows.filter((r) => {
      if (aksiFilter !== "all" && (r.Aksi || "") !== aksiFilter) return false;
      const ts = (r.Timestamp || "").slice(0, 10);
      if (dateFrom && ts < dateFrom) return false;
      if (dateTo && ts > dateTo) return false;
      return true;
    });
  }, [logs, aksiFilter, dateFrom, dateTo]);

  useEffect(() => {
    setPage(1);
  }, [aksiFilter, dateFrom, dateTo]);

  const paged = useMemo(
    () => filtered.slice((page - 1) * pageSize, page * pageSize),
    [filtered, page, pageSize]
  );

  return (
    <div className="page" data-testid="sejarah-page">
      <header className="page-header">
        <h1 className="title">Sejarah Aktivitas</h1>
        <p className="subtitle">Log aktivitas sistem (terbaru di atas)</p>
      </header>

      <section className="card">
        <div className="filter-bar">
          <div className="field">
            <span className="label">Aksi</span>
            <select
              className="filter-select"
              value={aksiFilter}
              onChange={(e) => setAksiFilter(e.target.value)}
              data-testid="sejarah-filter-aksi"
            >
              <option value="all">Semua</option>
              {AKSI_OPTIONS.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <span className="label">Dari</span>
            <input
              type="date"
              className="filter-select"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              data-testid="sejarah-date-from"
            />
          </div>
          <div className="field">
            <span className="label">Sampai</span>
            <input
              type="date"
              className="filter-select"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              data-testid="sejarah-date-to"
            />
          </div>
        </div>

        {loading && <Spinner testid="sejarah-loading" />}
        {!loading && error && (
          <div className="alert" data-testid="sejarah-error">{error}</div>
        )}
        {!loading && !error && filtered.length === 0 && (
          <p className="muted" data-testid="sejarah-empty">Tidak ada log yang cocok.</p>
        )}
        {!loading && !error && filtered.length > 0 && (
          <>
            <div className="table-scroll">
              <table className="table" data-testid="sejarah-table">
                <thead>
                  <tr>
                    <th>Waktu</th>
                    <th>User</th>
                    <th>Aksi</th>
                    <th>Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {paged.map((r, i) => (
                    <tr key={i} data-testid={`sejarah-row-${i}`}>
                      <td className="mono">{fmtWaktu(r.Timestamp)}</td>
                      <td>{r.User}</td>
                      <td>
                        <span className="badge badge-ijin">{r.Aksi}</span>
                      </td>
                      <td>{r.Detail}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              total={filtered.length}
              page={page}
              pageSize={pageSize}
              onPage={setPage}
              onSize={(n) => {
                setPageSize(n);
                setPage(1);
              }}
              testid="sejarah-pagination"
            />
          </>
        )}
      </section>
    </div>
  );
};

export default SejarahPage;
