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
  BarChart3,
  ThumbsUp,
  ThumbsDown,
  ClipboardList,
  Check,
  X,
  MessageSquare,
} from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { AuditEvent, FeedbackItem, FeedbackStats, User } from '../types';

export const AdminPage: React.FC = () => {
  const { isAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState<'users' | 'audit' | 'quality'>('users');
  const [users, setUsers] = useState<User[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditEvent[]>([]);
  const [feedbacks, setFeedbacks] = useState<FeedbackItem[]>([]);
  const [feedbackStats, setFeedbackStats] = useState<FeedbackStats | null>(null);
  const [feedbackFilter, setFeedbackFilter] = useState<{ rating?: string; status?: string }>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Triage Modal state
  const [triageItem, setTriageItem] = useState<FeedbackItem | null>(null);
  const [triageStatus, setTriageStatus] = useState<string>('in_review');
  const [triageNotes, setTriageNotes] = useState<string>('');
  const [isTriaging, setIsTriaging] = useState<boolean>(false);

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

  const fetchQualityData = async () => {
    setLoading(true);
    try {
      const [stats, list] = await Promise.all([
        api.feedback.getStats(),
        api.feedback.list({
          rating: feedbackFilter.rating || undefined,
          review_status: feedbackFilter.status || undefined,
          limit: 100,
        }),
      ]);
      setFeedbackStats(stats);
      setFeedbacks(list);
    } catch (err: any) {
      setError(err?.message || 'Failed to load quality and feedback data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!isAdmin) return;
    if (activeTab === 'users') {
      fetchUsers();
    } else if (activeTab === 'audit') {
      fetchAuditLogs();
    } else if (activeTab === 'quality') {
      fetchQualityData();
    }
  }, [isAdmin, activeTab, feedbackFilter]);

  const handleOpenTriage = (item: FeedbackItem) => {
    setTriageItem(item);
    setTriageStatus(item.review_status === 'pending_review' ? 'in_review' : item.review_status);
    setTriageNotes(item.reviewer_notes || '');
  };

  const handleSaveTriage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!triageItem) return;

    setIsTriaging(true);
    try {
      const updated = await api.feedback.updateReview(triageItem.id, {
        review_status: triageStatus,
        reviewer_notes: triageNotes.trim() || undefined,
      });

      setFeedbacks((prev) => prev.map((f) => (f.id === updated.id ? updated : f)));
      // Refresh stats in background
      api.feedback.getStats().then(setFeedbackStats).catch(() => {});
      setTriageItem(null);
    } catch (err: any) {
      alert(err?.message || 'Failed to update review task');
    } finally {
      setIsTriaging(false);
    }
  };

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
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 size={10} /> Allow
          </span>
        );
      case 'deny':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-50 text-red-700 border border-red-200">
            <XCircle size={10} /> Deny
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-700">
            {outcome}
          </span>
        );
    }
  };

  const getReviewStatusBadge = (status: string) => {
    switch (status) {
      case 'pending_review':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <AlertTriangle size={10} /> Pending Triage
          </span>
        );
      case 'in_review':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            <RefreshCw size={10} className="animate-spin" /> In Review
          </span>
        );
      case 'resolved':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <Check size={10} /> Resolved
          </span>
        );
      case 'dismissed':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-600">
            <X size={10} /> Dismissed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-500">
            {status}
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
            Real-time compliance monitoring, identity directory, and continuous quality evaluation.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              if (activeTab === 'users') fetchUsers();
              else if (activeTab === 'audit') fetchAuditLogs();
              else fetchQualityData();
            }}
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
          <button
            onClick={() => setActiveTab('quality')}
            className={`py-3.5 border-b-2 flex items-center gap-2 transition-colors cursor-pointer ${
              activeTab === 'quality'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <BarChart3 size={16} />
            <span>Quality & Human Reviews ({feedbackStats?.pending_reviews_count || 0} Pending)</span>
          </button>
        </div>

        {/* Tab 1: Users */}
        {activeTab === 'users' && (
          <div className="p-6">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
                  <th className="py-3 px-4">User Email</th>
                  <th className="py-3 px-3">Department</th>
                  <th className="py-3 px-3">Roles</th>
                  <th className="py-3 px-3">Superuser</th>
                  <th className="py-3 px-4 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700 text-xs">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="py-3 px-4 font-semibold text-slate-900">{u.email}</td>
                    <td className="py-3 px-3">
                      {u.department ? (
                        <span className="px-2 py-0.5 rounded-full bg-slate-100 font-medium text-slate-700 text-[11px]">
                          {u.department.name}
                        </span>
                      ) : (
                        <span className="text-slate-400 italic">None</span>
                      )}
                    </td>
                    <td className="py-3 px-3">
                      <div className="flex flex-wrap gap-1">
                        {u.roles?.map((r) => (
                          <span
                            key={r.id}
                            className="px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 font-medium text-[11px]"
                          >
                            {r.name}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      {u.is_superuser ? (
                        <span className="text-emerald-600 font-semibold text-[11px]">Yes</span>
                      ) : (
                        <span className="text-slate-400 text-[11px]">No</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      {u.is_active ? (
                        <span className="inline-flex items-center gap-1 text-emerald-600 font-medium text-[11px]">
                          <CheckCircle2 size={12} /> Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-red-500 font-medium text-[11px]">
                          <XCircle size={12} /> Inactive
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab 2: Audit Logs */}
        {activeTab === 'audit' && (
          <div className="p-6">
            <table className="w-full text-left border-collapse">
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
                    <td
                      className="py-3 px-3 text-slate-500 truncate max-w-[120px]"
                      title={log.actor_user_id || 'System'}
                    >
                      {log.actor_user_id ? `${log.actor_user_id.slice(0, 8)}...` : 'Anonymous'}
                    </td>
                    <td
                      className="py-3 px-3 text-slate-600 font-sans truncate max-w-[200px]"
                      title={log.details || log.resource_id || ''}
                    >
                      {log.details || log.resource_id || '—'}
                    </td>
                    <td
                      className="py-3 px-3 text-slate-400 truncate max-w-[100px]"
                      title={log.request_id || ''}
                    >
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
          </div>
        )}

        {/* Tab 3: Quality & Evaluation Dashboard (Phase 14) */}
        {activeTab === 'quality' && (
          <div className="p-6 space-y-6">
            {/* KPI Metric Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="p-4 rounded-xl border border-slate-200 bg-white shadow-xs">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                  Total Submissions
                </span>
                <span className="text-2xl font-extrabold text-slate-900">
                  {feedbackStats?.total_feedback || 0}
                </span>
                <p className="text-[10px] text-slate-400 mt-1">Recorded across all users</p>
              </div>

              <div className="p-4 rounded-xl border border-slate-200 bg-white shadow-xs">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                  Satisfaction Rate
                </span>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-extrabold text-emerald-600">
                    {feedbackStats ? (feedbackStats.satisfaction_rate * 100).toFixed(1) : 0}%
                  </span>
                  <span className="text-xs text-slate-500">
                    ({feedbackStats?.positive_count || 0} positive)
                  </span>
                </div>
                <p className="text-[10px] text-slate-400 mt-1">Thumbs-up rating proportion</p>
              </div>

              <div className="p-4 rounded-xl border border-slate-200 bg-white shadow-xs">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                  Negative Ratings
                </span>
                <span className="text-2xl font-extrabold text-rose-600">
                  {feedbackStats?.negative_count || 0}
                </span>
                <p className="text-[10px] text-slate-400 mt-1">Requiring diagnostic triage</p>
              </div>

              <div className="p-4 rounded-xl border border-slate-200 bg-white shadow-xs">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                  Pending Human Reviews
                </span>
                <span className="text-2xl font-extrabold text-amber-600">
                  {feedbackStats?.pending_reviews_count || 0}
                </span>
                <p className="text-[10px] text-slate-400 mt-1">
                  {feedbackStats?.resolved_reviews_count || 0} resolved tasks
                </p>
              </div>
            </div>

            {/* Failure Categories Breakdown */}
            {feedbackStats && feedbackStats.failure_categories && Object.keys(feedbackStats.failure_categories).length > 0 && (
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/60">
                <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <AlertTriangle size={13} className="text-amber-500" />
                  Failure Reason Distribution
                </h3>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(feedbackStats.failure_categories).map(([tag, count]) => (
                    <span
                      key={tag}
                      className="px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-xs font-medium text-slate-700 shadow-2xs flex items-center gap-1.5"
                    >
                      <span className="capitalize">{tag.replace('_', ' ')}:</span>
                      <strong className="text-rose-600 font-bold">{count}</strong>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Human Review Tasks & Feedback Table */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                  <ClipboardList size={16} className="text-indigo-600" />
                  Feedback Triage & Human Review Tasks
                </h3>

                {/* Filter Controls */}
                <div className="flex items-center gap-2 text-xs">
                  <select
                    value={feedbackFilter.status || ''}
                    onChange={(e) => setFeedbackFilter((prev) => ({ ...prev, status: e.target.value || undefined }))}
                    className="px-2.5 py-1.5 bg-white border border-slate-200 rounded-lg text-slate-700 focus:outline-hidden text-xs"
                  >
                    <option value="">All Review Statuses</option>
                    <option value="pending_review">Pending Review</option>
                    <option value="in_review">In Review</option>
                    <option value="resolved">Resolved</option>
                    <option value="dismissed">Dismissed</option>
                  </select>

                  <select
                    value={feedbackFilter.rating || ''}
                    onChange={(e) => setFeedbackFilter((prev) => ({ ...prev, rating: e.target.value || undefined }))}
                    className="px-2.5 py-1.5 bg-white border border-slate-200 rounded-lg text-slate-700 focus:outline-hidden text-xs"
                  >
                    <option value="">All Ratings</option>
                    <option value="negative">Negative Only</option>
                    <option value="positive">Positive Only</option>
                  </select>
                </div>
              </div>

              {feedbacks.length === 0 ? (
                <div className="p-8 text-center bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-500">
                  No feedback submissions match the current filter criteria.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
                        <th className="py-3 px-4">User</th>
                        <th className="py-3 px-3">Rating</th>
                        <th className="py-3 px-3">Question & Answer</th>
                        <th className="py-3 px-3">Reason Tags & Comments</th>
                        <th className="py-3 px-3">Review Status</th>
                        <th className="py-3 px-4 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                      {feedbacks.map((fb) => (
                        <tr key={fb.id} className="hover:bg-slate-50/60 transition-colors">
                          <td className="py-3 px-4">
                            <span className="font-semibold text-slate-900 block truncate max-w-[150px]" title={fb.user_email || ''}>
                              {fb.user_email || 'User'}
                            </span>
                            <span className="text-[10px] text-slate-400">
                              {fb.user_department || 'General'}
                            </span>
                          </td>
                          <td className="py-3 px-3">
                            {fb.rating === 'positive' ? (
                              <span className="inline-flex items-center gap-1 text-emerald-600 font-bold text-[11px]">
                                <ThumbsUp size={12} className="fill-emerald-100" /> Positive
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-rose-600 font-bold text-[11px]">
                                <ThumbsDown size={12} className="fill-rose-100" /> Negative
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-3 max-w-xs">
                            <p className="font-medium text-slate-800 truncate" title={fb.query_text}>
                              {fb.query_text}
                            </p>
                            <p className="text-[11px] text-slate-500 line-clamp-1 truncate" title={fb.answer_text}>
                              {fb.answer_text}
                            </p>
                          </td>
                          <td className="py-3 px-3 max-w-xs">
                            {fb.reason_tags && fb.reason_tags.length > 0 ? (
                              <div className="flex flex-wrap gap-1 mb-1">
                                {fb.reason_tags.map((t) => (
                                  <span
                                    key={t}
                                    className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-rose-50 text-rose-700 border border-rose-200 capitalize"
                                  >
                                    {t.replace('_', ' ')}
                                  </span>
                                ))}
                              </div>
                            ) : null}
                            {fb.comment && (
                              <p className="text-[11px] text-slate-600 italic line-clamp-1" title={fb.comment}>
                                "{fb.comment}"
                              </p>
                            )}
                          </td>
                          <td className="py-3 px-3">
                            {getReviewStatusBadge(fb.review_status)}
                          </td>
                          <td className="py-3 px-4 text-right">
                            {fb.rating === 'negative' && (
                              <button
                                onClick={() => handleOpenTriage(fb)}
                                className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 transition-colors cursor-pointer"
                              >
                                Triage
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Human Review Triage Modal */}
      {triageItem && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                <ClipboardList size={16} className="text-indigo-600" />
                Triage Review Task
              </h3>
              <button
                onClick={() => setTriageItem(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200/60"
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleSaveTriage} className="p-6 space-y-4">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs space-y-1">
                <div>
                  <strong className="text-slate-700">Question: </strong>
                  <span className="text-slate-600">{triageItem.query_text}</span>
                </div>
                <div>
                  <strong className="text-slate-700">User Comment: </strong>
                  <span className="text-slate-600">{triageItem.comment || 'None'}</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Review Status
                </label>
                <select
                  value={triageStatus}
                  onChange={(e) => setTriageStatus(e.target.value)}
                  className="w-full p-2.5 text-xs rounded-xl border border-slate-300 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 text-slate-800 bg-white"
                >
                  <option value="pending_review">Pending Review</option>
                  <option value="in_review">In Review (Assigning to Document Owner)</option>
                  <option value="resolved">Resolved (Documentation or Prompt Updated)</option>
                  <option value="dismissed">Dismissed (Working as Intended / Unsupported Query)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1.5">
                  <MessageSquare size={13} className="text-slate-400" />
                  Reviewer Investigation Notes
                </label>
                <textarea
                  rows={3}
                  value={triageNotes}
                  onChange={(e) => setTriageNotes(e.target.value)}
                  placeholder="Record corrective actions taken (e.g. updated Section 4 of runbook, resolved grant issue)..."
                  className="w-full p-2.5 text-xs rounded-xl border border-slate-300 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 text-slate-800"
                />
              </div>

              <div className="pt-2 border-t border-slate-100 flex items-center justify-end gap-2 text-xs">
                <button
                  type="button"
                  onClick={() => setTriageItem(null)}
                  disabled={isTriaging}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isTriaging}
                  className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold cursor-pointer disabled:opacity-50"
                >
                  {isTriaging ? 'Saving...' : 'Update Task'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
