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
import { Pie, Bar } from 'react-chartjs-2';

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
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, appsRes] = await Promise.all([
          apiClient.get("/applications/stats"),
          apiClient.get("/applications?limit=5")
        ]);
        setStats(statsRes.data);
        setRecentApps(appsRes.data.applications);
      } catch (error) {
        console.error("Failed to fetch dashboard data:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

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
          'rgba(16, 185, 129, 0.6)',
          'rgba(129, 140, 248, 0.6)',
          'rgba(248, 113, 113, 0.6)',
        ],
        borderColor: [
          '#00f2ff',
          '#10b981',
          '#818cf8',
          '#f87171',
        ],
        borderWidth: 1,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    plugins: {
      legend: {
        position: 'bottom' as const,
        labels: {
          color: '#888',
          font: { size: 10 }
        }
      },
    },
  };

  return (
    <div className="animate-fade-in">
      <div className={styles.grid}>
        {statCards.map((stat, i) => (
          <div key={i} className={`${styles.card} glass`}>
            <span className={styles.cardLabel}>{stat.label}</span>
            <span className={styles.cardValue}>{stat.value}</span>
            <span className={`${styles.cardTrend} ${stat.up ? styles.trendUp : styles.trendDown}`}>
              {stat.trend}
            </span>
          </div>
        ))}
      </div>

      <div className={styles.dashboardBody}>
        <div className={styles.mainSection}>
          <div className={styles.sectionHeader}>
            <h3 className="title">Recent Activity</h3>
            <button className="glass" style={{ padding: '0.5rem 1rem', fontSize: '0.8rem', cursor: 'pointer' }}>View All</button>
          </div>
          
          <div className="glass" style={{ overflow: 'hidden' }}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Job Title</th>
                  <th>Company</th>
                  <th>Portal</th>
                  <th>Match Score</th>
                  <th>Status</th>
                  <th>Applied At</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={6} style={{ textAlign: 'center', padding: '2rem' }}>Loading activity...</td></tr>
                ) : recentApps.length === 0 ? (
                  <tr><td colSpan={6} style={{ textAlign: 'center', padding: '2rem' }}>No recent activity found.</td></tr>
                ) : (
                  recentApps.map((app) => (
                    <tr key={app.id}>
                      <td style={{ fontWeight: 500 }}>{app.job_title}</td>
                      <td style={{ color: 'var(--text-secondary)' }}>{app.company}</td>
                      <td>{app.portal}</td>
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
                      <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                        {new Date(app.applied_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        <aside className={styles.statsSidebar}>
          <div className={`${styles.chartCard} glass`}>
            <h4 className={styles.chartTitle}>Applications by Portal</h4>
            <div className={styles.chartWrapper}>
              {stats ? <Pie data={pieData} options={chartOptions} /> : <p>Loading chart...</p>}
            </div>
          </div>

          <div className={`${styles.infoCard} glass`}>
            <h4>System Health</h4>
            <div className={styles.healthItem}>
              <span>API Server</span>
              <span className={styles.healthStatus}>Online</span>
            </div>
            <div className={styles.healthItem}>
              <span>Celery Workers</span>
              <span className={styles.healthStatus}>Active</span>
            </div>
            <div className={styles.healthItem}>
              <span>Redis Broker</span>
              <span className={styles.healthStatus}>Connected</span>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
