export const Spinner = ({ label = "Memuat data…", testid }) => (
  <div className="spinner-wrap" data-testid={testid}>
    <span className="spinner" aria-hidden="true" />
    <span className="muted">{label}</span>
  </div>
);
