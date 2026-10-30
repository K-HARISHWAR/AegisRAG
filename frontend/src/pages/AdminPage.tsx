import React, { useEffect, useState } from 'react';
import {
  Settings,
  Users,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Lock,
} from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { AuditEvent, User } from '../types';

export const AdminPage: React.FC = () => {
  const { isAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState<'users' | 'audit'>('users');
  const [users, setUsers] = useState<User[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const data = await api.admin.listUsers();
      setUsers(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch users list');
    } finally {
      setLoading(false);
    }
  };

  const fetchAuditLogs = async () => {
    setLoading(true);
    try {
      const data = await api.admin.listAuditLogs(100, 0);
      setAuditLogs(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch security audit logs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!isAdmin) return;
    if (activeTab === 'users') {
      fetchUsers();
    } else {
      fetchAuditLogs();
    }
  }, [isAdmin, activeTab]);

  if (!isAdmin) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16 text-center">
        <div className="w-12 h-12 rounded-2xl bg-red-100 text-red-600 flex items-center justify-center mx-auto mb-4">
          <Lock size={24} />
        </div>
        <h2 className="text-lg font-bold text-slate-900 mb-1">Access Restricted</h2>
        <p className="text-xs text-slate-500">
          The Admin Console is strictly reserved for verified system administrators.
        </p>
      </div>
    );
  }

  const getOutcomeBadge = (outcome: string) => {
    switch (outcome.toLowerCase()) {
      case 'allow':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 size={11} /> Allow
          </span>
        );
      case 'deny':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-red-50 text-red-700 border border-red-200">
            <XCircle size={11} /> Deny
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <AlertTriangle size={11} /> {outcome}
          </span>
        );
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Page Title */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Settings className="text-indigo-600" size={24} />
            Security & Administration Console
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Real-time compliance monitoring, identity directory, and tamper-resistant audit trail.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => (activeTab === 'users' ? fetchUsers() : fetchAuditLogs())}
            disabled={loading}
            className="px-3 py-1.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold shadow-xs flex items-center gap-1.5 cursor-pointer transition-colors"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-800">
          {error}
        </div>
      )}

      {/* Tabs */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="flex border-b border-slate-200 px-6 gap-6 text-xs font-semibold bg-slate-50/50">
          <button
            onClick={() => setActiveTab('users')}
            className={`py-3.5 border-b-2 flex items-center gap-2 transition-colors cursor-pointer ${
              activeTab === 'users'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Users size={16} />
            <span>User Directory ({users.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('audit')}
            className={`py-3.5 border-b-2 flex items-center gap-2 transition-colors cursor-pointer ${
              activeTab === 'audit'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <ShieldCheck size={16} />
            <span>Security Audit Log ({auditLogs.length})</span>
          </button>
        </div>

        {/* Tab 1: Users Table */}
        {activeTab === 'users' && (
          <div className="overflow-x-auto">
            {loading ? (
              <div className="py-16 text-center text-slate-400 text-xs">
                <span className="inline-block w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mb-2" />
                <p>Loading user directory...</p>
              </div>
            ) : (
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
                    <th className="py-3 px-4">User</th>
                    <th className="py-3 px-3">Department</th>
                    <th className="py-3 px-3">Assigned Roles</th>
                    <th className="py-3 px-3">Status</th>
                    <th className="py-3 px-4">Created Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {users.map((u) => (
                    <tr key={u.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="py-3.5 px-4">
                        <div className="font-semibold text-slate-900">{u.email}</div>
                        <span className="text-[10px] text-slate-400 font-mono">ID: {u.id}</span>
                      </td>
                      <td className="py-3.5 px-3">
                        <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700">
                          {u.department?.name || 'Unassigned'}
                        </span>
                      </td>
                      <td className="py-3.5 px-3">
                        <div className="flex gap-1 flex-wrap">
                          {u.roles.map((r) => (
                            <span
                              key={r.id}
                              className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                                r.name === 'admin'
                                  ? 'bg-red-50 text-red-700 border border-red-200'
                                  : r.name === 'department_manager'
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  : 'bg-blue-50 text-blue-700 border border-blue-200'
                              }`}
                            >
                              {r.name}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="py-3.5 px-3">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium ${
                            u.is_active
                              ? 'bg-emerald-50 text-emerald-700'
                              : 'bg-red-50 text-red-700'
                          }`}
                        >
                          <span className="w-1.5 h-1.5 rounded-full bg-current" />
                          {u.is_active ? 'Active' : 'Disabled'}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-slate-500 text-[11px]">
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* Tab 2: Audit Logs Table */}
        {activeTab === 'audit' && (
          <div className="overflow-x-auto">
            {loading ? (
              <div className="py-16 text-center text-slate-400 text-xs">
                <span className="inline-block w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mb-2" />
                <p>Loading security audit stream...</p>
              </div>
            ) : auditLogs.length === 0 ? (
              <div className="py-16 text-center text-slate-400 text-xs">
                <ShieldCheck size={32} className="mx-auto mb-2 text-slate-300" />
                <p>No audit events recorded yet.</p>
              </div>
            ) : (
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
                    <th className="py-3 px-4">Action</th>
                    <th className="py-3 px-3">Outcome</th>
                    <th className="py-3 px-3">Actor ID</th>
                    <th className="py-3 px-3">Details / Resource</th>
                    <th className="py-3 px-3">Request ID</th>
                    <th className="py-3 px-4 text-right">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700 font-mono text-[11px]">
                  {auditLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="py-3 px-4 font-semibold text-slate-900 font-sans">
                        {log.action}
                      </td>
                      <td className="py-3 px-3">{getOutcomeBadge(log.outcome)}</td>
                      <td className="py-3 px-3 text-slate-500 truncate max-w-[120px]" title={log.actor_user_id || 'System'}>
                        {log.actor_user_id ? `${log.actor_user_id.slice(0, 8)}...` : 'Anonymous'}
                      </td>
                      <td className="py-3 px-3 text-slate-600 font-sans truncate max-w-[200px]" title={log.details || log.resource_id || ''}>
                        {log.details || log.resource_id || '—'}
                      </td>
                      <td className="py-3 px-3 text-slate-400 truncate max-w-[100px]" title={log.request_id || ''}>
                        {log.request_id ? `${log.request_id.slice(0, 8)}...` : '—'}
                      </td>
                      <td className="py-3 px-4 text-right text-slate-500">
                        {new Date(log.timestamp).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit',
                        })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
