import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Layout } from "./Layout";
import { Spinner } from "./Spinner";

export const ProtectedRoute = ({ children }) => {
  const { user } = useAuth();
  if (user === undefined)
    return (
      <div className="page">
        <Spinner label="Memuat…" testid="auth-checking" />
      </div>
    );
  if (!user) return <Navigate to="/login" replace />;
  return <Layout>{children}</Layout>;
};
