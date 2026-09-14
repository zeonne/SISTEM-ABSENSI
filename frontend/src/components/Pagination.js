import { PAGE_SIZES } from "../lib/format";

export const Pagination = ({ total, page, pageSize, onPage, onSize, testid }) => {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="pagination" data-testid={testid}>
      <div className="page-size">
        <span className="label">Baris per halaman</span>
        <select
          className="filter-select"
          value={pageSize}
          onChange={(e) => onSize(Number(e.target.value))}
          data-testid={`${testid}-size`}
        >
          {PAGE_SIZES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>
      <div className="page-nav">
        <button
          className="btn btn-secondary btn-sm"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          data-testid={`${testid}-prev`}
        >
          Sebelumnya
        </button>
        <span className="page-info" data-testid={`${testid}-info`}>
          Hal {page} / {totalPages} ({total} data)
        </span>
        <button
          className="btn btn-secondary btn-sm"
          disabled={page >= totalPages}
          onClick={() => onPage(page + 1)}
          data-testid={`${testid}-next`}
        >
          Selanjutnya
        </button>
      </div>
    </div>
  );
};
