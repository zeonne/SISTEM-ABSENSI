import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import Login from "./pages/Login";
import DashboardPage from "./pages/DashboardPage";
import AbsensiPage from "./pages/AbsensiPage";
import SiswaPage from "./pages/SiswaPage";
import SejarahPage from "./pages/SejarahPage";

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
                  <AbsensiPage />
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
            <Route
              path="/sejarah"
              element={
                <ProtectedRoute>
                  <SejarahPage />
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
