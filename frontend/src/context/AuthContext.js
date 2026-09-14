import { createContext, useContext, useEffect, useState } from "react";
import axios, { API } from "../lib/api";

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(undefined); // undefined=checking, null=guest, object=logged in

  useEffect(() => {
    const id = axios.interceptors.response.use(
      (r) => r,
      (error) => {
        if (error?.response?.status === 401) setUser(null);
        return Promise.reject(error);
      }
    );
    return () => axios.interceptors.response.eject(id);
  }, []);

  useEffect(() => {
    axios
      .get(`${API}/me`)
      .then((res) => setUser(res.data.user))
      .catch(() => setUser(null));
  }, []);

  const logout = async () => {
    try {
      await axios.post(`${API}/logout`);
    } catch (e) {
      /* ignore */
    }
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, setUser, logout }}>
      {children}
    </AuthContext.Provider>
  );
};
