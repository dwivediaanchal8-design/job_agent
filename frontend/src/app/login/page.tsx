"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import styles from "./login.module.css";
import apiClient from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await apiClient.post("/auth/login", {
        email: email,
        password: password,
      });

      if (response.data.access_token) {
        localStorage.setItem("token", response.data.access_token);
        router.push("/");
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Access denied. Check credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={`${styles.loginCard} glass animate-fade-in`}>
        <div className={styles.logo}>
          <span className={styles.logoIcon}>⚡</span>
          <h1 className={styles.logoText}>Antigravity</h1>
        </div>
        
        <h2 className={styles.title}>System Access</h2>
        <p className={styles.subtitle}>Initialize neural link to dashboard</p>

        <form className={styles.form} onSubmit={handleLogin}>
          <div className={styles.inputGroup}>
            <label htmlFor="email">Neural Identifier (Email)</label>
            <input
              id="email"
              type="email"
              placeholder="admin@jobagent.ai"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className={styles.inputGroup}>
            <label htmlFor="password">Security Protocol (Password)</label>
            <input
              id="password"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {error && <div className={styles.error}>{error}</div>}

          <button type="submit" className={styles.loginButton} disabled={loading}>
            {loading ? "Decrypting..." : "Initialize Command"}
          </button>
        </form>

        <div className={styles.footer}>
          <p>Autonomous Pipeline v1.0.0</p>
        </div>
      </div>
    </div>
  );
}
