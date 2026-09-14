import { useState } from "react";
import { useNavigate, NavLink } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";

const linkClass = ({ isActive }) => "nav-link" + (isActive ? " nav-link-active" : "");

export const Sidebar = ({ mobileOpen, onClose }) => {
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  const [confirmOpen, setConfirmOpen] = useState(false);

  const doLogout = async () => {
    setConfirmOpen(false);
    await logout();
    toast.success("Berhasil logout");
    navigate("/login", { replace: true });
  };

  const handleNav = () => {
    if (onClose) onClose();
  };

  return (
    <>
      {mobileOpen && (
        <div className="sidebar-backdrop" onClick={onClose} data-testid="sidebar-backdrop" />
      )}
      <aside
        className={"sidebar" + (mobileOpen ? " sidebar-open" : "")}
        data-testid="sidebar"
      >
        <div className="sidebar-brand">
          <span className="brand-mark">SA</span>
          <div>
            <div className="brand-title">Absensi Sekolah</div>
            <div className="brand-user">{user?.nama || user?.username}</div>
          </div>
        </div>
        <nav className="sidebar-nav">
          <NavLink to="/dashboard" className={linkClass} onClick={handleNav} data-testid="nav-dashboard">
            Dashboard
          </NavLink>
          <NavLink to="/absensi" className={linkClass} onClick={handleNav} data-testid="nav-absensi">
            Absensi
          </NavLink>
          <NavLink to="/siswa" className={linkClass} onClick={handleNav} data-testid="nav-siswa">
            Siswa
          </NavLink>
          <NavLink to="/sejarah" className={linkClass} onClick={handleNav} data-testid="nav-sejarah">
            Sejarah Aktivitas
          </NavLink>
        </nav>
        <button
          className="nav-logout"
          onClick={() => setConfirmOpen(true)}
          data-testid="nav-logout"
        >
          Logout
        </button>
      </aside>

      {confirmOpen && (
        <div className="modal-overlay" data-testid="logout-confirm">
          <div className="modal-card confirm-card">
            <h2 className="card-title">Konfirmasi Logout</h2>
            <p className="muted">Apakah kamu yakin ingin keluar?</p>
            <div className="modal-actions">
              <button
                className="btn btn-secondary"
                onClick={() => setConfirmOpen(false)}
                data-testid="logout-cancel"
              >
                Batal
              </button>
              <button
                className="btn btn-danger"
                onClick={doLogout}
                data-testid="logout-confirm-yes"
              >
                Ya, Keluar
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
