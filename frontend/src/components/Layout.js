import { useState } from "react";
import { Menu } from "lucide-react";
import { Sidebar } from "./Sidebar";

export const Layout = ({ children }) => {
  const [mobileOpen, setMobileOpen] = useState(false);
  return (
    <div className="app-shell">
      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
      <div className="app-main-wrap">
        <div className="mobile-topbar">
          <button
            className="hamburger"
            onClick={() => setMobileOpen(true)}
            aria-label="Buka menu"
            data-testid="mobile-menu-btn"
          >
            <Menu size={22} />
          </button>
          <span className="mobile-brand">Absensi Sekolah</span>
        </div>
        <main className="app-main">{children}</main>
      </div>
    </div>
  );
};
