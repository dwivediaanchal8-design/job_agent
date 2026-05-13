"use client";

import { useEffect, useState } from "react";
import styles from "./applications.module.css";
import apiClient from "@/lib/api";

export default function ApplicationsPage() {
  const [apps, setApps] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");
  const [portalFilter, setPortalFilter] = useState("");

  const fetchApplications = async () => {
    setLoading(true);
    try {
      let url = "/applications?limit=50";
      if (statusFilter) url += `&status=${statusFilter}`;
      if (portalFilter) url += `&portal=${portalFilter}`;
      
      const response = await apiClient.get(url);
      setApps(response.data.applications);
      setTotal(response.data.total);
    } catch (error) {
      console.error("Failed to fetch applications", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApplications();
  }, [statusFilter, portalFilter]);

  return (
    <div className="animate-fade-in">
      <div className={styles.filters}>
        <div className={styles.filterGroup}>
          <label>Status</label>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="glass">
            <option value="">All Statuses</option>
            <option value="applied">Applied</option>
            <option value="failed">Failed</option>
            <option value="skipped">Skipped</option>
          </select>
        </div>
        <div className={styles.filterGroup}>
          <label>Portal</label>
          <select value={portalFilter} onChange={(e) => setPortalFilter(e.target.value)} className="glass">
            <option value="">All Portals</option>
            <option value="Indeed">Indeed</option>
            <option value="LinkedIn">LinkedIn</option>
            <option value="Dice">Dice</option>
          </select>
        </div>
        <div className={styles.stats}>
          <span>Showing <strong>{apps.length}</strong> of <strong>{total}</strong> applications</span>
        </div>
      </div>

      <div className="glass" style={{ overflow: 'hidden' }}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Job Title</th>
              <th>Company</th>
              <th>Portal</th>
              <th>Score</th>
              <th>Status</th>
              <th>Applied Date</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} style={{ textAlign: 'center', padding: '3rem' }}>Loading applications...</td></tr>
            ) : apps.length === 0 ? (
              <tr><td colSpan={7} style={{ textAlign: 'center', padding: '3rem' }}>No applications match your filters.</td></tr>
            ) : (
              apps.map((app) => (
                <tr key={app.id}>
                  <td>
                    <div className={styles.jobTitle}>{app.job_title}</div>
                    <a href={app.job_url} target="_blank" rel="noopener noreferrer" className={styles.jobLink}>View Job</a>
                  </td>
                  <td>{app.company}</td>
                  <td>{app.portal}</td>
                  <td>
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
                  <td>{new Date(app.applied_at).toLocaleDateString()}</td>
                  <td>
                    <button className={styles.viewBtn}>Details</button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
