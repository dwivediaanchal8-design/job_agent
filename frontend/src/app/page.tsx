"use client";

import { useEffect, useState } from "react";
import styles from "./page.module.css";
import apiClient from "@/lib/api";
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
} from 'chart.js';
import { Pie } from 'react-chartjs-2';

ChartJS.register(
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  BarElement,
  Title
);

export default function Home() {
  const [stats, setStats] = useState<any>(null);
  const [recentApps, setRecentApps] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningAgent, setRunningAgent] = useState(false);
  
  // Selection state for manual run
  const [selectedUser, setSelectedUser] = useState("");
  const [selectedPortal, setSelectedPortal] = useState("dice");
  const [dryRun, setDryRun] = useState(true);

  const fetchData = async () => {
    try {
      const [statsRes, appsRes, usersRes] = await Promise.all([
        apiClient.get("/applications/stats"),
        apiClient.get("/applications?limit=8"),
        apiClient.get("/users")
      ]);
      setStats(statsRes.data);
      setRecentApps(appsRes.data.applications);
      setUsers(Array.isArray(usersRes.data) ? usersRes.data : []);
      if (Array.isArray(usersRes.data) && usersRes.data.length > 0 && !selectedUser) {
        setSelectedUser(usersRes.data[0].id);
      }
    } catch (error: any) {
      console.error("Failed to fetch dashboard data:", error);
      if (error.response?.status === 401) {
        window.location.href = "/login";
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // Poll for stats every 30 seconds
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleRunAgent = async () => {
    if (!selectedUser) return;
    
    setRunningAgent(true);
    try {
      const res = await apiClient.post("/jobs/run", {
        user_id: selectedUser,
        portal: selectedPortal,
        dry_run: dryRun
      });
      alert(`Task Dispatched! ID: ${res.data.task_id}`);
    } catch (error: any) {
      alert(`Error: ${error.response?.data?.detail || error.message}`);
    } finally {
      setRunningAgent(false);
    }
  };

  const statCards = stats ? [
    { label: "Today's Total", value: stats.total_today, trend: "Real-time", up: true },
    { label: "Today's Applied", value: stats.applied_today, trend: `${Math.round((stats.applied_today / (stats.total_today || 1)) * 100)}% Success`, up: true },
    { label: "All-Time Apps", value: stats.total_all_time, trend: "Growth", up: true },
    { label: "Today's Failed", value: stats.failed_today, trend: "Review needed", up: false },
  ] : [
    { label: "Today's Total", value: "0", trend: "...", up: true },
    { label: "Today's Applied", value: "0", trend: "...", up: true },
    { label: "All-Time Apps", value: "0", trend: "...", up: true },
    { label: "Today's Failed", value: "0", trend: "...", up: false },
  ];

  const pieData = {
    labels: stats ? Object.keys(stats.portals_breakdown) : ['None'],
    datasets: [
      {
        label: '# of Applications',
        data: stats ? Object.values(stats.portals_breakdown) : [0],
        backgroundColor: [
          'rgba(0, 242, 255, 0.6)',
          'rgba(129, 140, 248, 0.6)',
          'rgba(16, 185, 129, 0.6)',
          'rgba(248, 113, 113, 0.6)',
        ],
        borderColor: [
          '#00f2ff',
          '#818cf8',
          '#10b981',
          '#f87171',
        ],
        borderWidth: 1,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom' as const,
        labels: {
          color: '#94a3b8',
          font: { size: 11, family: 'Outfit' },
          padding: 20
        }
      },
    },
  };

  return (
    <div className="animate-fade-in">
      <div style={{ marginBottom: '2rem' }}>
        <h1 className="title-gradient" style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>Autonomous Job Command</h1>
        <p className="subtitle">Real-time monitoring and automation control system</p>
      </div>

      <div className={styles.grid}>
        {statCards.map((stat, i) => (
          <div key={i} className={`${styles.card} glass glass-hover`}>
            <span className={styles.cardLabel}>{stat.label}</span>
            <span className={styles.cardValue}>{stat.value}</span>
            <span className={`${styles.cardTrend} ${stat.up ? styles.trendUp : styles.trendDown}`}>
              {stat.up ? '↑' : '↓'} {stat.trend}
            </span>
          </div>
        ))}
      </div>

      <div className={styles.dashboardBody}>
        <div className={styles.mainSection}>
          <div className="glass" style={{ padding: '2rem' }}>
            <div className={styles.sectionHeader}>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 600 }}>Recent Activity</h3>
              <button className="btn-secondary" style={{ padding: '0.4rem 1rem', fontSize: '0.8rem' }}>Export Data</button>
            </div>
            
            <div className={styles.tableContainer}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Job Title</th>
                    <th>Company</th>
                    <th>Portal</th>
                    <th>Score</th>
                    <th>Status</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr><td colSpan={6} style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>Initialising neural link...</td></tr>
                  ) : recentApps.length === 0 ? (
                    <tr><td colSpan={6} style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>No recent data pulses detected.</td></tr>
                  ) : (
                    recentApps.map((app) => (
                      <tr key={app.id}>
                        <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{app.job_title}</td>
                        <td style={{ color: 'var(--text-secondary)' }}>{app.company}</td>
                        <td><span style={{ textTransform: 'uppercase', fontSize: '0.7rem', fontWeight: 700, color: 'var(--accent-secondary)' }}>{app.portal}</span></td>
                        <td className={styles.score}>
                          <span className={app.match_score >= 80 ? styles.scoreHigh : app.match_score >= 60 ? styles.scoreMedium : styles.scoreLow}>
                            {Math.round(app.match_score || 0)}%
                          </span>
                        </td>
                        <td>
                          <span className={`${styles.status} ${
                            app.status === 'applied' ? styles.statusApplied : 
                            app.status === 'failed' ? styles.statusFailed : 
                            styles.statusSkipped
                          }`}>
                            {app.status}
                          </span>
                        </td>
                        <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                          {new Date(app.applied_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <aside className={styles.statsSidebar}>
          <div className={`${styles.sidebarCard} glass`}>
            <h4 className={styles.sidebarTitle}>
              <span style={{ color: 'var(--accent-primary)' }}>●</span> Manual Command
            </h4>
            <div className={styles.controlPanel}>
              <div className="input-group">
                <label>Target User</label>
                <select value={selectedUser} onChange={(e) => setSelectedUser(e.target.value)}>
                  <option value="">Select User...</option>
                  {Array.isArray(users) && users.map(u => <option key={u.id} value={u.id}>{u.full_name}</option>)}
                </select>
              </div>
              <div className="input-group">
                <label>Job Portal</label>
                <select value={selectedPortal} onChange={(e) => setSelectedPortal(e.target.value)}>
                  <option value="dice">Dice</option>
                  <option value="indeed">Indeed</option>
                  <option value="linkedin">LinkedIn</option>
                </select>
              </div>
              <div className="input-group" style={{ flexDirection: 'row', alignItems: 'center', gap: '0.5rem' }}>
                <input 
                  type="checkbox" 
                  id="dryRun" 
                  checked={dryRun} 
                  onChange={(e) => setDryRun(e.target.checked)}
                  style={{ width: 'auto' }}
                />
                <label htmlFor="dryRun" style={{ marginBottom: 0 }}>Dry Run (Simulation)</label>
              </div>
              <button 
                className="btn-primary controlAction" 
                onClick={handleRunAgent}
                disabled={runningAgent || !selectedUser}
              >
                {runningAgent ? "Processing..." : "Execute Pipeline"}
              </button>
            </div>
          </div>

          <div className={`${styles.sidebarCard} glass`}>
            <h4 className={styles.sidebarTitle}>Portal Distribution</h4>
            <div className={styles.chartWrapper}>
              {stats ? <Pie data={pieData} options={chartOptions} /> : <p>Loading...</p>}
            </div>
          </div>

          <div className={`${styles.sidebarCard} glass`}>
            <h4 className={styles.sidebarTitle}>System Nodes</h4>
            <div className={styles.healthList}>
              <div className={styles.healthItem}>
                <span className={styles.healthLabel}>API Engine</span>
                <span className={styles.healthStatus}><span className={styles.healthDot}></span> Active</span>
              </div>
              <div className={styles.healthItem}>
                <span className={styles.healthLabel}>Neural Worker</span>
                <span className={styles.healthStatus}><span className={styles.healthDot}></span> Processing</span>
              </div>
              <div className={styles.healthItem}>
                <span className={styles.healthLabel}>Redis Sync</span>
                <span className={styles.healthStatus}><span className={styles.healthDot}></span> Synced</span>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
