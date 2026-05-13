"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import "./globals.css";
import styles from "./layout.module.css";
import Link from "next/link";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const router = useRouter();
  const pathname = usePathname();
  const [isAuth, setIsAuth] = useState(false);

  useEffect(() => {
    const token = typeof window !== 'undefined' ? localStorage.getItem("token") : null;
    if (!token && pathname !== "/login") {
      router.push("/login");
    } else if (token && pathname === "/login") {
      router.push("/");
    }
    
    if (token) {
      setIsAuth(true);
    } else {
      setIsAuth(false);
    }
  }, [pathname, router]);

  const handleLogout = () => {
    localStorage.removeItem("token");
    router.push("/login");
  };

  // Don't show sidebar/topbar on login page
  if (pathname === "/login") {
    return (
      <html lang="en">
        <body>{children}</body>
      </html>
    );
  }

  return (
    <html lang="en">
      <body>
        <div className={styles.layout}>
          <aside className={styles.sidebar}>
            <div className={styles.logo}>
              <span className={styles.logoIcon}>🤖</span>
              <span className={styles.logoText}>JobAgent</span>
            </div>
            <nav className={styles.nav}>
              <Link href="/" className={`${styles.navLink} ${pathname === "/" ? styles.active : ""}`}>Dashboard</Link>
              <Link href="/users" className={`${styles.navLink} ${pathname === "/users" ? styles.active : ""}`}>Users</Link>
              <Link href="/applications" className={`${styles.navLink} ${pathname === "/applications" ? styles.active : ""}`}>Applications</Link>
              <Link href="/logs" className={`${styles.navLink} ${pathname === "/logs" ? styles.active : ""}`}>Logs</Link>
            </nav>
            <div className={styles.sidebarFooter}>
              <button onClick={handleLogout} className={styles.logoutBtn}>Logout</button>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '1rem' }}>v1.0.0</p>
            </div>
          </aside>
          <main className={styles.mainContent}>
            <header className={`${styles.topbar} glass`}>
              <div className={styles.topbarLeft}>
                <h2 className="title">
                  {pathname === "/" ? "Dashboard Overview" : 
                   pathname === "/users" ? "User Management" : 
                   pathname === "/applications" ? "Application History" : 
                   pathname === "/logs" ? "System Logs" : "JobAgent"}
                </h2>
              </div>
              <div className={styles.topbarRight}>
                <div className={styles.userProfile}>
                  <span className={styles.userName}>Admin</span>
                  <div className={styles.userAvatar}>AD</div>
                </div>
              </div>
            </header>
            <div className={styles.contentInner}>
              {children}
            </div>
          </main>
        </div>
      </body>
    </html>
  );
}
