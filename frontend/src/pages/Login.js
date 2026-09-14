import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import axios, { API } from "../lib/api";
import { useAuth } from "../context/AuthContext";

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

export default Login;
