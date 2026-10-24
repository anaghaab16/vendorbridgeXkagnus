import { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api.js";

const AuthCtx = createContext(null);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(!!localStorage.getItem("token"));

  useEffect(() => {
    if (!localStorage.getItem("token")) return;
    api("/auth/me").then(setUser).catch(() => localStorage.removeItem("token")).finally(() => setLoading(false));
  }, []);

  async function login(email, password) {
    const { access_token } = await api("/auth/login", { method: "POST", body: { email, password } });
    localStorage.setItem("token", access_token);
    setUser(await api("/auth/me"));
  }
  const register = (data) => api("/auth/register", { method: "POST", body: data });
  function logout() { localStorage.removeItem("token"); setUser(null); }

  return <AuthCtx.Provider value={{ user, loading, login, register, logout }}>{children}</AuthCtx.Provider>;
}
