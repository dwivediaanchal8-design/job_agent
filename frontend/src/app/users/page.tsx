"use client";

import { useEffect, useState } from "react";
import styles from "./users.module.css";
import apiClient from "@/lib/api";

export default function UsersPage() {
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [error, setError] = useState("");
  
  // New user form state
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("job_seeker");

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get("/users/");
      // The backend returns { users: [], total: 0 }
      setUsers(response.data.users || []);
    } catch (error) {
      console.error("Failed to fetch users", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleAddUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await apiClient.post("/users", {
        full_name: fullName,
        email: email,
        password: password,
        role: role
      });
      setShowModal(false);
      fetchUsers();
      // Reset form
      setFullName("");
      setEmail("");
      setPassword("");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to add user");
    }
  };

  const toggleUserStatus = async (user: any) => {
    try {
      await apiClient.patch(`/users/${user.id}`, {
        is_active: !user.is_active
      });
      fetchUsers();
    } catch (err) {
      console.error("Failed to toggle user status", err);
    }
  };

  return (
    <div className="animate-fade-in">
      <div className={styles.header}>
        <h1 className="title">User Management</h1>
        <button className={styles.addButton} onClick={() => setShowModal(true)}>
          <span>+</span> Add New User
        </button>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem' }}>Loading users...</div>
      ) : users.length === 0 ? (
        <div className="glass" style={{ textAlign: 'center', padding: '3rem' }}>
          <p>No users found. Create your first job-seeker account!</p>
        </div>
      ) : (
        <div className={styles.userGrid}>
          {users.map((user) => (
            <div key={user.id} className={`${styles.userCard} glass`}>
              <div className={styles.userHeader}>
                <div className={styles.avatar}>
                  {user.full_name.charAt(0)}
                </div>
                <div className={styles.info}>
                  <h3>{user.full_name}</h3>
                  <p>{user.email}</p>
                </div>
              </div>

              <div className={styles.details}>
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>Status</span>
                  <span className={`${styles.badge} ${user.is_active ? styles.badgeActive : styles.badgeInactive}`}>
                    {user.is_active ? "Active" : "Inactive"}
                  </span>
                </div>
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>Role</span>
                  <span className={styles.detailValue} style={{ textTransform: 'capitalize' }}>
                    {user.role.replace('_', ' ')}
                  </span>
                </div>
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>Joined</span>
                  <span className={styles.detailValue}>{new Date(user.created_at).toLocaleDateString()}</span>
                </div>
              </div>

              <div className={styles.actions}>
                <button 
                  className={styles.actionButton} 
                  onClick={() => toggleUserStatus(user)}
                >
                  {user.is_active ? "Deactivate" : "Activate"}
                </button>
                <button className={styles.actionButton}>Manage Data</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <div className={styles.modalOverlay}>
          <div className={`${styles.modal} glass animate-scale-up`}>
            <h2>Add New User</h2>
            {error && <p className={styles.error}>{error}</p>}
            <form onSubmit={handleAddUser} className={styles.form}>
              <div className={styles.inputGroup}>
                <label>Full Name</label>
                <input 
                  type="text" 
                  placeholder="John Doe" 
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required 
                />
              </div>
              <div className={styles.inputGroup}>
                <label>Email Address</label>
                <input 
                  type="email" 
                  placeholder="john@example.com" 
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required 
                />
              </div>
              <div className={styles.inputGroup}>
                <label>Initial Password</label>
                <input 
                  type="password" 
                  placeholder="••••••••" 
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required 
                />
              </div>
              <div className={styles.inputGroup}>
                <label>Role</label>
                <select value={role} onChange={(e) => setRole(e.target.value)}>
                  <option value="job_seeker">Job Seeker</option>
                  <option value="admin">Administrator</option>
                </select>
              </div>
              <div className={styles.modalActions}>
                <button type="button" className={styles.cancelBtn} onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className={styles.submitBtn}>Create User</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
