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
  Download,
  Key,
  ShieldAlert,
  Filter,
  Activity,
  Zap,
  Clock,
  Coins,
  Trash2,
  Layers,
  Cpu,
  Database,
  AlertCircle,
  ToggleLeft,
  ToggleRight,
  Archive,
  RotateCw,
} from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import {
  AccessReviewReport,
  AuditEvent,
  AuditIntegrityReport,
  FeedbackItem,
  FeedbackStats,
  OperationsMetricsResponse,
  QuotaStatusResponse,
  RequestTraceRead,
  FeatureFlagsState,
  DisasterRecoveryStatus,
  User,
} from '../types';

export const AdminPage: React.FC = () => {
  const { isAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState<'users' | 'audit' | 'access_review' | 'quality' | 'operations'>('users');
  const [users, setUsers] = useState<User[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditEvent[]>([]);
  const [integrityReport, setIntegrityReport] = useState<AuditIntegrityReport | null>(null);
  const [isVerifyingIntegrity, setIsVerifyingIntegrity] = useState<boolean>(false);
  const [isExportingAudit, setIsExportingAudit] = useState<boolean>(false);
  const [accessReview, setAccessReview] = useState<AccessReviewReport | null>(null);
  const [auditActionFilter, setAuditActionFilter] = useState<string>('');
  const [auditOutcomeFilter, setAuditOutcomeFilter] = useState<string>('');
  const [feedbacks, setFeedbacks] = useState<FeedbackItem[]>([]);
  const [feedbackStats, setFeedbackStats] = useState<FeedbackStats | null>(null);
  const [feedbackFilter, setFeedbackFilter] = useState<{ rating?: string; status?: string }>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Operations & Performance state
  const [operationsMetrics, setOperationsMetrics] = useState<OperationsMetricsResponse | null>(null);
  const [traces, setTraces] = useState<RequestTraceRead[]>([]);
  const [selectedTrace, setSelectedTrace] = useState<RequestTraceRead | null>(null);
  const [quotaStatus, setQuotaStatus] = useState<QuotaStatusResponse | null>(null);
  const [isPurgingCache, setIsPurgingCache] = useState<boolean>(false);
  const [cachePurgedMsg, setCachePurgedMsg] = useState<string | null>(null);
  const [featureFlags, setFeatureFlags] = useState<FeatureFlagsState | null>(null);
  const [drStatus, setDrStatus] = useState<DisasterRecoveryStatus | null>(null);
  const [isBackingUp, setIsBackingUp] = useState<boolean>(false);
  const [isRebuildingIndex, setIsRebuildingIndex] = useState<boolean>(false);
  const [drActionMsg, setDrActionMsg] = useState<string | null>(null);

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
      const [logs, integrity] = await Promise.all([
        api.admin.listAuditLogs({
          limit: 100,
          offset: 0,
          action: auditActionFilter || undefined,
          outcome: auditOutcomeFilter || undefined,
        }),
        api.admin.verifyAuditIntegrity().catch(() => null),
      ]);
      setAuditLogs(logs);
      if (integrity) setIntegrityReport(integrity);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch security audit logs');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyIntegrity = async () => {
    setIsVerifyingIntegrity(true);
    try {
      const res = await api.admin.verifyAuditIntegrity();
      setIntegrityReport(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to verify audit hash integrity');
    } finally {
      setIsVerifyingIntegrity(false);
    }
  };

  const handleExportAudit = async () => {
    setIsExportingAudit(true);
    try {
      const data = await api.admin.exportAudit(500, 0);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `aegisrag-audit-export-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err?.message || 'Failed to export audit log');
    } finally {
      setIsExportingAudit(false);
    }
  };

  const fetchAccessReview = async () => {
    setLoading(true);
    try {
      const data = await api.admin.getAccessReview();
      setAccessReview(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch access review report');
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

  const fetchOperationsData = async () => {
    setLoading(true);
    try {
      const [metrics, traceList, quotas, flags, dr] = await Promise.all([
        api.operations.getMetrics(),
        api.operations.getTraces(50),
        api.operations.getQuotas().catch(() => null),
        api.operations.getFeatureFlags().catch(() => null),
        api.operations.getDisasterRecoveryStatus().catch(() => null),
      ]);
      setOperationsMetrics(metrics);
      setTraces(traceList);
      if (quotas) setQuotaStatus(quotas);
      if (flags) setFeatureFlags(flags);
      if (dr) setDrStatus(dr);
    } catch (err: any) {
      setError(err?.message || 'Failed to load operations metrics, feature flags, or disaster recovery data');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleFlag = async (flagName: keyof FeatureFlagsState, currentVal: boolean) => {
    try {
      const updated = await api.operations.updateFeatureFlags({ [flagName]: !currentVal });
      setFeatureFlags(updated);
      setDrActionMsg(`Feature flag '${flagName}' updated to ${!currentVal}`);
      setTimeout(() => setDrActionMsg(null), 3000);
    } catch (err: any) {
      setError(err?.message || 'Failed to update feature flag');
    }
  };

  const handleResetFlags = async () => {
    if (!window.confirm('Reset all runtime feature flags to system configuration defaults?')) return;
    try {
      const res = await api.operations.resetFeatureFlags();
      setFeatureFlags(res);
      setDrActionMsg('All feature flags successfully reset to defaults.');
      setTimeout(() => setDrActionMsg(null), 4000);
    } catch (err: any) {
      setError(err?.message || 'Failed to reset feature flags');
    }
  };

  const handleCreateBackup = async () => {
    setIsBackingUp(true);
    try {
      const res = await api.operations.createBackup();
      setDrActionMsg(`Snapshot backup created: ${res.filename} (${(res.size_bytes / 1024).toFixed(1)} KB)`);
      setTimeout(() => setDrActionMsg(null), 5000);
      const updatedDr = await api.operations.getDisasterRecoveryStatus().catch(() => null);
      if (updatedDr) setDrStatus(updatedDr);
    } catch (err: any) {
      setError(err?.message || 'Failed to create database snapshot backup');
    } finally {
      setIsBackingUp(false);
    }
  };

  const handleRebuildIndex = async () => {
    if (!window.confirm('Wipe and completely rebuild vector store index from authoritative PostgreSQL records? This may take several moments.')) return;
    setIsRebuildingIndex(true);
    try {
      const res = await api.operations.rebuildIndex();
      setDrActionMsg(`Vector store index rebuilt: ${res.documents_processed} documents, ${res.chunks_indexed} chunks re-indexed in ${res.duration_ms}ms.`);
      setTimeout(() => setDrActionMsg(null), 6000);
      const updatedDr = await api.operations.getDisasterRecoveryStatus().catch(() => null);
      if (updatedDr) setDrStatus(updatedDr);
    } catch (err: any) {
      setError(err?.message || 'Failed to rebuild vector store');
    } finally {
      setIsRebuildingIndex(false);
    }
  };

  const handleClearCache = async () => {
    if (!window.confirm('Are you sure you want to purge the safe scoped cache? All users will experience fresh generation on subsequent queries.')) {
      return;
    }
    setIsPurgingCache(true);
    try {
      const res = await api.operations.clearCache();
      setCachePurgedMsg(res.message);
      setTimeout(() => setCachePurgedMsg(null), 4000);
      fetchOperationsData();
    } catch (err: any) {
      setError(err?.message || 'Failed to clear scoped cache');
    } finally {
      setIsPurgingCache(false);
    }
  };

  useEffect(() => {
    if (!isAdmin) return;
    if (activeTab === 'users') {
      fetchUsers();
    } else if (activeTab === 'audit') {
      fetchAuditLogs();
    } else if (activeTab === 'access_review') {
      fetchAccessReview();
    } else if (activeTab === 'quality') {
      fetchQualityData();
    } else if (activeTab === 'operations') {
      fetchOperationsData();
    }
  }, [isAdmin, activeTab, feedbackFilter, auditActionFilter, auditOutcomeFilter]);

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
              else if (activeTab === 'access_review') fetchAccessReview();
              else if (activeTab === 'quality') fetchQualityData();
              else if (activeTab === 'operations') fetchOperationsData();
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
            <span>Audit Trail & Tamper Chain ({auditLogs.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('access_review')}
            className={`py-3.5 border-b-2 flex items-center gap-2 transition-colors cursor-pointer ${
              activeTab === 'access_review'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Key size={16} />
            <span>Access Review & Governance</span>
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
          <button
            onClick={() => setActiveTab('operations')}
            className={`py-3.5 border-b-2 flex items-center gap-2 transition-colors cursor-pointer ${
              activeTab === 'operations'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Activity size={16} />
            <span>Operations & Performance ({traces.length})</span>
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

        {/* Tab 2: Audit Logs & Cryptographic Tamper Chain */}
        {activeTab === 'audit' && (
          <div className="p-6 space-y-6">
            {/* Hash Chain Integrity Status Card */}
            <div
              className={`p-4 rounded-xl border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 ${
                integrityReport?.is_valid === false
                  ? 'bg-rose-50 border-rose-200 text-rose-900'
                  : 'bg-emerald-50/50 border-emerald-200 text-emerald-900'
              }`}
            >
              <div className="flex items-center gap-3">
                <div
                  className={`p-2.5 rounded-lg ${
                    integrityReport?.is_valid === false
                      ? 'bg-rose-100 text-rose-700'
                      : 'bg-emerald-100 text-emerald-700'
                  }`}
                >
                  {integrityReport?.is_valid === false ? (
                    <ShieldAlert size={22} />
                  ) : (
                    <ShieldCheck size={22} />
                  )}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="text-xs font-bold uppercase tracking-wider">
                      {integrityReport?.is_valid === false
                        ? 'Audit Trail Tampering Detected!'
                        : 'Cryptographic Hash Chain: Verified'}
                    </h4>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-white/80 border">
                      SHA-256
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 mt-0.5">
                    {integrityReport?.is_valid === false
                      ? `Alert: ${integrityReport.tampered_event_ids.length} records have payload or sequence mutations.`
                      : `All ${integrityReport?.total_events_checked ?? auditLogs.length} audit trail events are cryptographically chained and tamper-free.`}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={handleVerifyIntegrity}
                  disabled={isVerifyingIntegrity}
                  className="px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold shadow-xs flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  <RefreshCw size={12} className={isVerifyingIntegrity ? 'animate-spin' : ''} />
                  <span>Verify Chain</span>
                </button>
                <button
                  onClick={handleExportAudit}
                  disabled={isExportingAudit}
                  className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  <Download size={12} />
                  <span>{isExportingAudit ? 'Exporting...' : 'Export Audit (JSON)'}</span>
                </button>
              </div>
            </div>

            {/* Filter Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs">
              <div className="flex flex-wrap items-center gap-3">
                <div className="flex items-center gap-1.5 text-slate-500 font-medium">
                  <Filter size={13} />
                  <span>Filters:</span>
                </div>
                <select
                  value={auditActionFilter}
                  onChange={(e) => setAuditActionFilter(e.target.value)}
                  className="px-2.5 py-1.5 bg-white border border-slate-300 rounded-md text-xs text-slate-700 focus:outline-hidden"
                >
                  <option value="">All Actions</option>
                  <option value="login">User Login</option>
                  <option value="create_grant">Create Grant</option>
                  <option value="revoke_grant">Revoke Grant</option>
                  <option value="rag_generation">RAG Generation</option>
                  <option value="retrieval_query">Retrieval Query</option>
                  <option value="upload_document">Upload Document</option>
                  <option value="delete_document">Delete Document</option>
                  <option value="export_audit_trail">Export Audit</option>
                </select>

                <select
                  value={auditOutcomeFilter}
                  onChange={(e) => setAuditOutcomeFilter(e.target.value)}
                  className="px-2.5 py-1.5 bg-white border border-slate-300 rounded-md text-xs text-slate-700 focus:outline-hidden"
                >
                  <option value="">All Outcomes</option>
                  <option value="allow">Allow (Permitted)</option>
                  <option value="deny">Deny (Rejected)</option>
                  <option value="error">Error</option>
                </select>
              </div>

              <div className="text-[11px] text-slate-500 font-mono">
                Showing {auditLogs.length} events
              </div>
            </div>

            {/* Audit Log Table */}
            <div className="overflow-x-auto border border-slate-200 rounded-lg">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
                    <th className="py-3 px-3">Seq / Chain Hash</th>
                    <th className="py-3 px-4">Action & Reason</th>
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
                      <td className="py-3 px-3">
                        <div className="flex items-center gap-1.5 font-bold text-slate-700">
                          <span>#{log.sequence_number ?? '1'}</span>
                          <span
                            className="text-[10px] text-slate-400 truncate max-w-[80px]"
                            title={`Event Hash: ${log.event_hash || 'Unchained'}`}
                          >
                            {log.event_hash ? `${log.event_hash.slice(0, 8)}...` : '—'}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-4 font-sans">
                        <div className="font-semibold text-slate-900">{log.action}</div>
                        {log.policy_reason_code && (
                          <span className="inline-block px-1.5 py-0.2 bg-slate-100 text-slate-600 rounded text-[9px] font-mono mt-0.5">
                            {log.policy_reason_code}
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-3 font-sans">{getOutcomeBadge(log.outcome)}</td>
                      <td
                        className="py-3 px-3 text-slate-500 truncate max-w-[120px]"
                        title={log.actor_user_id || 'System'}
                      >
                        {log.actor_user_id ? `${log.actor_user_id.slice(0, 8)}...` : 'System'}
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
                      <td className="py-3 px-4 text-right text-slate-500 font-sans">
                        {new Date(log.timestamp).toLocaleString([], {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit',
                        })}
                      </td>
                    </tr>
                  ))}
                  {auditLogs.length === 0 && (
                    <tr>
                      <td colSpan={7} className="py-12 text-center text-slate-400 font-sans text-xs">
                        No audit events match the specified filters.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tab 3: Access Review & Governance (Phase 17) */}
        {activeTab === 'access_review' && (
          <div className="p-6 space-y-6">
            {/* Header info */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 pb-4">
              <div>
                <h3 className="text-base font-semibold text-slate-800">
                  Governance Authorization Matrix
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Inspect role hierarchies, active explicit document grants, and policy enforcement denials.
                </p>
              </div>
              <div className="text-[11px] text-slate-400">
                Generated: {accessReview ? new Date(accessReview.generated_at).toLocaleTimeString() : '—'}
              </div>
            </div>

            {/* Privilege Anomalies Alert */}
            {accessReview && accessReview.privilege_anomalies.length > 0 && (
              <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900 space-y-1.5">
                <div className="flex items-center gap-2 font-semibold">
                  <AlertTriangle size={16} className="text-amber-600 shrink-0" />
                  <span>Privilege Anomalies Detected ({accessReview.privilege_anomalies.length})</span>
                </div>
                <ul className="list-disc list-inside text-[11px] text-amber-800 space-y-0.5 pl-1">
                  {accessReview.privilege_anomalies.map((anom, idx) => (
                    <li key={idx}>{anom}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Roles Breakdown */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-3 flex items-center gap-1.5">
                <Users size={14} className="text-indigo-600" />
                <span>Role Hierarchy & Permissions</span>
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {accessReview?.roles_summary.map((r) => (
                  <div key={r.role_id} className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-900 capitalize text-sm">{r.role_name}</span>
                      <span className="px-2 py-0.5 bg-indigo-50 text-indigo-700 font-semibold rounded text-[11px] border border-indigo-200">
                        {r.users_count} users
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500">{r.description || 'System role'}</p>
                    <div className="pt-2 border-t border-slate-200/60 space-y-1">
                      <div className="text-[10px] font-bold uppercase text-slate-400">Granted Privileges</div>
                      <div className="flex flex-wrap gap-1">
                        {r.permissions.map((p, pIdx) => (
                          <span
                            key={pIdx}
                            className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-white border border-slate-200 text-slate-600"
                          >
                            {p}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Explicit Grants Matrix */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-3 flex items-center gap-1.5">
                <Key size={14} className="text-indigo-600" />
                <span>Active Explicit Document Grants ({accessReview?.explicit_grants.length || 0})</span>
              </h4>
              <div className="overflow-x-auto border border-slate-200 rounded-lg">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-50 text-slate-500 uppercase text-[11px] font-semibold border-b border-slate-200">
                      <th className="py-2.5 px-3">Document Title</th>
                      <th className="py-2.5 px-3">Department</th>
                      <th className="py-2.5 px-3">Grantee Type</th>
                      <th className="py-2.5 px-3">Grantee Identifier</th>
                      <th className="py-2.5 px-3">Permission</th>
                      <th className="py-2.5 px-3 text-right">Granted Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {accessReview?.explicit_grants.map((g) => (
                      <tr key={g.grant_id} className="hover:bg-slate-50/60">
                        <td className="py-3 px-3 font-medium text-slate-900">{g.document_title}</td>
                        <td className="py-3 px-3 text-slate-500">{g.department_name}</td>
                        <td className="py-3 px-3 uppercase text-[10px] font-mono font-semibold text-slate-500">
                          {g.grantee_type}
                        </td>
                        <td className="py-3 px-3 font-mono text-[11px] text-slate-800">{g.grantee_label}</td>
                        <td className="py-3 px-3">
                          <span className="px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded text-[10px] font-semibold border border-emerald-200">
                            {g.permission.toUpperCase()}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-right text-slate-500">
                          {new Date(g.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                    {(!accessReview?.explicit_grants || accessReview.explicit_grants.length === 0) && (
                      <tr>
                        <td colSpan={6} className="py-8 text-center text-slate-400">
                          No explicit document grants currently active.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Recent Policy Denials */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-3 flex items-center gap-1.5">
                <ShieldAlert size={14} className="text-rose-600" />
                <span>Recent Policy Denials Telemetry</span>
              </h4>
              <div className="overflow-x-auto border border-slate-200 rounded-lg">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-50 text-slate-500 uppercase text-[11px] font-semibold border-b border-slate-200">
                      <th className="py-2.5 px-3">Timestamp</th>
                      <th className="py-2.5 px-3">Action</th>
                      <th className="py-2.5 px-3">Reason Code</th>
                      <th className="py-2.5 px-3">Actor ID</th>
                      <th className="py-2.5 px-3">Safe Explanation</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {accessReview?.recent_denials.map((d, dIdx) => (
                      <tr key={dIdx} className="hover:bg-slate-50/60">
                        <td className="py-3 px-3 text-slate-500">
                          {new Date(d.timestamp).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </td>
                        <td className="py-3 px-3 font-semibold text-slate-900">{d.action}</td>
                        <td className="py-3 px-3 font-mono text-[10px] text-rose-700">
                          {d.policy_reason_code || 'DENIED'}
                        </td>
                        <td className="py-3 px-3 font-mono text-[11px] text-slate-500">
                          {d.actor_user_id ? `${d.actor_user_id.slice(0, 8)}...` : 'Anonymous'}
                        </td>
                        <td className="py-3 px-3 text-slate-600">{d.safe_explanation}</td>
                      </tr>
                    ))}
                    {(!accessReview?.recent_denials || accessReview.recent_denials.length === 0) && (
                      <tr>
                        <td colSpan={5} className="py-8 text-center text-slate-400">
                          No recent policy denials recorded.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Tab 4: Quality & Evaluation Dashboard (Phase 14) */}
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

        {/* Tab 5: Operations & Performance */}
        {activeTab === 'operations' && (
          <div className="p-6 space-y-6">
            {/* System Alerts */}
            {operationsMetrics && operationsMetrics.active_alerts.length > 0 && (
              <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl space-y-2">
                <div className="flex items-center gap-2 text-amber-800 font-bold text-xs">
                  <AlertCircle size={16} />
                  <span>Active Operational Alerts ({operationsMetrics.active_alerts.length})</span>
                </div>
                <ul className="list-disc pl-5 text-xs text-amber-700 space-y-1">
                  {operationsMetrics.active_alerts.map((alert, idx) => (
                    <li key={idx}>{alert}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Cache Banner */}
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div>
                <h4 className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                  <Database size={14} className="text-indigo-600" />
                  Safe Policy-Scoped Cache Management
                </h4>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  Responses are cryptographically isolated per-tenant, per-user, and invalidated on document updates.
                </p>
                {cachePurgedMsg && (
                  <p className="text-[11px] text-emerald-600 font-semibold mt-1 flex items-center gap-1">
                    <CheckCircle2 size={12} /> {cachePurgedMsg}
                  </p>
                )}
              </div>
              <button
                onClick={handleClearCache}
                disabled={isPurgingCache}
                className="px-3 py-1.5 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-semibold flex items-center gap-1.5 cursor-pointer disabled:opacity-50 transition-colors"
              >
                <Trash2 size={13} />
                <span>{isPurgingCache ? 'Purging...' : 'Purge All Cached Answers'}</span>
              </button>
            </div>

            {/* KPI Cards */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              <div className="p-3.5 bg-white border border-slate-200 rounded-xl shadow-xs">
                <div className="text-[11px] font-medium text-slate-500 flex items-center gap-1">
                  <Activity size={13} className="text-indigo-600" /> Total Requests
                </div>
                <div className="text-lg font-bold text-slate-900 mt-1">
                  {operationsMetrics?.total_requests ?? 0}
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5">Traces recorded</div>
              </div>

              <div className="p-3.5 bg-white border border-slate-200 rounded-xl shadow-xs">
                <div className="text-[11px] font-medium text-slate-500 flex items-center gap-1">
                  <Zap size={13} className="text-emerald-600" /> Cache Hit Rate
                </div>
                <div className="text-lg font-bold text-emerald-700 mt-1">
                  {((operationsMetrics?.cache_hit_rate ?? 0) * 100).toFixed(1)}%
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5">Sub-millisecond retrieval</div>
              </div>

              <div className="p-3.5 bg-white border border-slate-200 rounded-xl shadow-xs">
                <div className="text-[11px] font-medium text-slate-500 flex items-center gap-1">
                  <ShieldAlert size={13} className="text-amber-600" /> Empty Result Rate
                </div>
                <div className="text-lg font-bold text-amber-700 mt-1">
                  {((operationsMetrics?.empty_result_rate ?? 0) * 100).toFixed(1)}%
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5">0 authorized chunks</div>
              </div>

              <div className="p-3.5 bg-white border border-slate-200 rounded-xl shadow-xs">
                <div className="text-[11px] font-medium text-slate-500 flex items-center gap-1">
                  <Lock size={13} className="text-blue-600" /> Abstention Rate
                </div>
                <div className="text-lg font-bold text-blue-700 mt-1">
                  {((operationsMetrics?.abstention_rate ?? 0) * 100).toFixed(1)}%
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5">Responsible refusals</div>
              </div>

              <div className="p-3.5 bg-white border border-slate-200 rounded-xl shadow-xs">
                <div className="text-[11px] font-medium text-slate-500 flex items-center gap-1">
                  <Cpu size={13} className="text-violet-600" /> Total Tokens
                </div>
                <div className="text-lg font-bold text-violet-700 mt-1">
                  {(operationsMetrics?.total_tokens ?? 0).toLocaleString()}
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5">Prompt & completion</div>
              </div>

              <div className="p-3.5 bg-white border border-slate-200 rounded-xl shadow-xs">
                <div className="text-[11px] font-medium text-slate-500 flex items-center gap-1">
                  <Coins size={13} className="text-amber-600" /> Estimated Cost
                </div>
                <div className="text-lg font-bold text-slate-900 mt-1">
                  ${(operationsMetrics?.total_estimated_cost_usd ?? 0).toFixed(4)}
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5">USD model pricing</div>
              </div>
            </div>

            {/* Quota Telemetry */}
            {quotaStatus && (
              <div className="p-4 bg-indigo-50/50 border border-indigo-100 rounded-xl flex flex-wrap items-center justify-between gap-4 text-xs">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-indigo-900">Your Identity Quota:</span>
                  <span className="px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-800 font-semibold uppercase text-[10px]">
                    {quotaStatus.role}
                  </span>
                  <span className="text-slate-600">({quotaStatus.email})</span>
                </div>
                <div className="flex items-center gap-4 text-slate-700 font-medium">
                  <div>
                    <span className="text-slate-400">Minute Remaining:</span>{' '}
                    <span className="font-bold text-indigo-700">{quotaStatus.requests_remaining_minute}</span> / {quotaStatus.rate_limit_per_minute}
                  </div>
                  <div>
                    <span className="text-slate-400">Daily Remaining:</span>{' '}
                    <span className="font-bold text-indigo-700">{quotaStatus.daily_queries_remaining}</span> / {quotaStatus.daily_quota}
                  </div>
                  <div>
                    <span className="text-slate-400">Reset in:</span>{' '}
                    <span className="font-bold text-slate-800">{Math.floor(quotaStatus.reset_seconds / 60)}m {quotaStatus.reset_seconds % 60}s</span>
                  </div>
                </div>
              </div>
            )}

            {/* Action notification banner */}
            {drActionMsg && (
              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={16} className="text-emerald-600" />
                  <span>{drActionMsg}</span>
                </div>
                <button onClick={() => setDrActionMsg(null)} className="text-emerald-500 hover:text-emerald-700 cursor-pointer">
                  <X size={14} />
                </button>
              </div>
            )}

            {/* Feature Flags & Disaster Recovery Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Feature Flags Panel */}
              <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <div>
                    <h4 className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                      <ToggleRight size={16} className="text-indigo-600" />
                      Runtime Server-Side Feature Flags
                    </h4>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      Gradual rollout and instant kill-switches. RBAC authorization is permanently fail-closed.
                    </p>
                  </div>
                  <button
                    onClick={handleResetFlags}
                    className="px-2.5 py-1 text-[11px] font-semibold rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors flex items-center gap-1 cursor-pointer"
                  >
                    <RotateCw size={11} /> Reset
                  </button>
                </div>

                {featureFlags ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                    {[
                      { key: 'enable_hybrid_retrieval', label: 'Hybrid BM25 Retrieval', desc: 'Dense + sparse lexical fusion' },
                      { key: 'enable_reranking', label: 'Cross-Encoder Reranking', desc: 'Deep candidate passage scoring' },
                      { key: 'enable_evidence_validation', label: 'Evidence Claim Validation', desc: 'Citation integrity & abstention' },
                      { key: 'enable_scoped_cache', label: 'Safe Policy-Scoped Cache', desc: 'Isolated per-identity response cache' },
                      { key: 'enable_rate_limiting', label: 'Identity Rate Limiting', desc: 'Sliding-window quota enforcement' },
                      { key: 'enable_tracing', label: 'Distributed Request Tracing', desc: 'Spans and stage latency profiling' },
                      { key: 'enable_workflows', label: 'Knowledge Workflows', desc: 'Diff, summarize, and extract' },
                      { key: 'enable_ocr', label: 'Scanned Document OCR', desc: 'Tesseract optical text extraction' },
                    ].map(({ key, label, desc }) => {
                      const enabled = (featureFlags as any)[key] ?? true;
                      return (
                        <div
                          key={key}
                          onClick={() => handleToggleFlag(key as any, enabled)}
                          className={`p-2.5 rounded-xl border flex items-center justify-between cursor-pointer transition-all ${
                            enabled
                              ? 'bg-indigo-50/40 border-indigo-200 hover:bg-indigo-50/70'
                              : 'bg-slate-50 border-slate-200 hover:bg-slate-100'
                          }`}
                        >
                          <div>
                            <div className="font-semibold text-slate-900 text-xs">{label}</div>
                            <div className="text-[10px] text-slate-500">{desc}</div>
                          </div>
                          <button
                            type="button"
                            className={`p-1 rounded-lg ${enabled ? 'text-indigo-600' : 'text-slate-400'}`}
                          >
                            {enabled ? <ToggleRight size={22} /> : <ToggleLeft size={22} />}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 py-3 text-center">Loading feature flags...</p>
                )}
              </div>

              {/* Disaster Recovery & Index Rebuild Panel */}
              <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
                <div className="border-b border-slate-100 pb-3">
                  <h4 className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                    <Archive size={16} className="text-indigo-600" />
                    Disaster Recovery & Vector Store Synchronization
                  </h4>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    PostgreSQL is authoritative. Vector collections can be completely wiped and rebuilt on demand.
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                    <div className="text-[10px] text-slate-400">PostgreSQL Active Chunks</div>
                    <div className="text-base font-bold text-slate-900 mt-0.5">
                      {drStatus?.database_active_chunks ?? 0}
                    </div>
                    <div className="text-[10px] text-emerald-600 font-semibold mt-0.5">Authoritative Source</div>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                    <div className="text-[10px] text-slate-400">Vector Store Health</div>
                    <div className="text-base font-bold text-slate-900 mt-0.5">
                      {drStatus?.vector_store_healthy ? (
                        <span className="text-emerald-600 flex items-center gap-1 text-sm font-semibold">
                          <CheckCircle2 size={14} /> Synchronized
                        </span>
                      ) : (
                        <span className="text-amber-600 text-sm font-semibold">Needs Rebuild</span>
                      )}
                    </div>
                    <div className="text-[10px] text-slate-400 mt-0.5">{drStatus?.recent_backups_count ?? 0} snapshots stored</div>
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row gap-2 pt-1">
                  <button
                    onClick={handleCreateBackup}
                    disabled={isBackingUp}
                    className="flex-1 px-3 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50 transition-colors"
                  >
                    <Archive size={13} />
                    <span>{isBackingUp ? 'Creating Backup...' : 'Create Snapshot Backup'}</span>
                  </button>
                  <button
                    onClick={handleRebuildIndex}
                    disabled={isRebuildingIndex}
                    className="flex-1 px-3 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50 transition-colors"
                  >
                    <RotateCw size={13} className={isRebuildingIndex ? 'animate-spin' : ''} />
                    <span>{isRebuildingIndex ? 'Rebuilding Index...' : 'Rebuild Vector Index'}</span>
                  </button>
                </div>

                {drStatus?.recent_backups && drStatus.recent_backups.length > 0 && (
                  <div className="pt-2 border-t border-slate-100">
                    <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                      Recent Snapshot Backups
                    </div>
                    <div className="space-y-1">
                      {drStatus.recent_backups.slice(0, 3).map((b) => (
                        <div key={b.filename} className="flex items-center justify-between text-[11px] font-mono text-slate-600 bg-slate-50 p-1.5 rounded">
                          <span className="truncate max-w-[200px]" title={b.filename}>{b.filename}</span>
                          <span className="text-slate-400">{(b.size_bytes / 1024).toFixed(1)} KB</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Stage Latencies & Slowest Stages */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Latency Table */}
              <div className="lg:col-span-2 bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
                <h4 className="text-xs font-bold text-slate-900 mb-3 flex items-center gap-1.5">
                  <Clock size={14} className="text-indigo-600" />
                  Stage Latency Profiling (p50, p95, Max)
                </h4>
                {operationsMetrics?.stage_latencies && operationsMetrics.stage_latencies.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-slate-200 text-slate-400 font-semibold uppercase text-[10px]">
                          <th className="py-2 px-3">Stage</th>
                          <th className="py-2 px-3">p50 Latency</th>
                          <th className="py-2 px-3">p95 Latency</th>
                          <th className="py-2 px-3">Max Latency</th>
                          <th className="py-2 px-3 text-right">Samples</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                        {operationsMetrics.stage_latencies.map((sl) => (
                          <tr key={sl.stage_name} className="hover:bg-slate-50/50">
                            <td className="py-2 px-3 font-sans font-semibold text-slate-800 capitalize">
                              {sl.stage_name.replace('_', ' ')}
                            </td>
                            <td className="py-2 px-3 text-slate-700">{sl.p50_ms.toFixed(1)} ms</td>
                            <td className="py-2 px-3 text-indigo-600 font-semibold">{sl.p95_ms.toFixed(1)} ms</td>
                            <td className="py-2 px-3 text-slate-500">{sl.max_ms.toFixed(1)} ms</td>
                            <td className="py-2 px-3 text-right font-sans text-slate-400">{sl.samples_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 py-4 text-center">No stage telemetry recorded yet.</p>
                )}
              </div>

              {/* Slowest Stage Distribution */}
              <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
                <h4 className="text-xs font-bold text-slate-900 mb-3 flex items-center gap-1.5">
                  <Layers size={14} className="text-indigo-600" />
                  Slowest Stage Frequency
                </h4>
                {operationsMetrics?.slowest_stages_distribution && Object.keys(operationsMetrics.slowest_stages_distribution).length > 0 ? (
                  <div className="space-y-2 text-xs">
                    {Object.entries(operationsMetrics.slowest_stages_distribution).map(([stage, count]) => (
                      <div key={stage} className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-100">
                        <span className="font-semibold text-slate-800 capitalize">{stage.replace('_', ' ')}</span>
                        <span className="px-2 py-0.5 rounded-full bg-slate-200 text-slate-800 font-mono text-[11px] font-bold">
                          {count} requests
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 py-4 text-center">No trace samples available.</p>
                )}
              </div>
            </div>

            {/* Recent Request Traces Waterfall Table */}
            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
              <h4 className="text-xs font-bold text-slate-900 mb-3 flex items-center gap-1.5">
                <Activity size={14} className="text-indigo-600" />
                Distributed Request Traces & Waterfall Inspector ({traces.length})
              </h4>
              {traces.length === 0 ? (
                <p className="text-xs text-slate-400 py-6 text-center">No traces recorded yet.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-500 font-semibold uppercase text-[10px]">
                        <th className="py-2.5 px-3">Correlation ID</th>
                        <th className="py-2.5 px-3">Latency</th>
                        <th className="py-2.5 px-3">Slowest Stage</th>
                        <th className="py-2.5 px-3">Tokens</th>
                        <th className="py-2.5 px-3">Est. Cost</th>
                        <th className="py-2.5 px-3">Status</th>
                        <th className="py-2.5 px-3 text-right">Spans Waterfall</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                      {traces.map((t) => (
                        <tr key={t.id} className="hover:bg-slate-50/50 transition-colors">
                          <td className="py-2.5 px-3 font-mono text-[11px] text-slate-800">
                            {t.request_id.slice(0, 18)}...
                          </td>
                          <td className="py-2.5 px-3 font-semibold text-slate-900">
                            {t.total_latency_ms.toFixed(1)} ms
                          </td>
                          <td className="py-2.5 px-3">
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200 capitalize">
                              {t.slowest_stage} ({t.slowest_stage_latency_ms.toFixed(0)}ms)
                            </span>
                          </td>
                          <td className="py-2.5 px-3 font-mono text-[11px] text-slate-600">
                            {t.total_tokens}
                          </td>
                          <td className="py-2.5 px-3 font-mono text-[11px] text-slate-600">
                            ${t.estimated_cost_usd.toFixed(5)}
                          </td>
                          <td className="py-2.5 px-3">
                            {t.error_type ? (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                                {t.error_type}
                              </span>
                            ) : t.is_abstained ? (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                                Abstained
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                Success
                              </span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 text-right">
                            <button
                              onClick={() => setSelectedTrace(t)}
                              className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 cursor-pointer transition-colors"
                            >
                              Inspect Spans ({t.spans?.length || 0})
                            </button>
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

      {/* Waterfall Trace Inspection Modal */}
      {selectedTrace && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-white rounded-2xl max-w-2xl w-full shadow-2xl border border-slate-200 overflow-hidden max-h-[90vh] flex flex-col">
            <div className="px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                  <Activity size={16} className="text-indigo-600" />
                  Request Trace Spans Waterfall
                </h3>
                <p className="text-[11px] font-mono text-slate-500 mt-0.5">
                  ID: {selectedTrace.request_id}
                </p>
              </div>
              <button
                onClick={() => setSelectedTrace(null)}
                className="p-1 rounded-lg hover:bg-slate-200 text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                <X size={16} />
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-4 text-xs">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-50 p-3 rounded-xl border border-slate-200 text-center">
                <div>
                  <div className="text-[10px] text-slate-400">Total Latency</div>
                  <div className="font-bold text-slate-900 mt-0.5">{selectedTrace.total_latency_ms.toFixed(1)} ms</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-400">Slowest Stage</div>
                  <div className="font-bold text-indigo-700 capitalize mt-0.5">{selectedTrace.slowest_stage}</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-400">Tokens (P / C)</div>
                  <div className="font-bold text-slate-900 mt-0.5">{selectedTrace.prompt_tokens} / {selectedTrace.completion_tokens}</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-400">Est. Cost</div>
                  <div className="font-bold text-slate-900 mt-0.5">${selectedTrace.estimated_cost_usd.toFixed(5)}</div>
                </div>
              </div>

              <div>
                <h4 className="font-bold text-slate-800 mb-2">Discrete Stage Spans</h4>
                {selectedTrace.spans && selectedTrace.spans.length > 0 ? (
                  <div className="space-y-2">
                    {selectedTrace.spans.map((span, sIdx) => {
                      const pct = Math.min(100, Math.max(6, Math.round((span.duration_ms / Math.max(1, selectedTrace.total_latency_ms)) * 100)));
                      return (
                        <div key={sIdx} className="p-2.5 rounded-lg border border-slate-200 bg-white">
                          <div className="flex items-center justify-between text-xs mb-1">
                            <span className="font-semibold text-slate-800 capitalize flex items-center gap-1.5">
                              <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                              {span.stage_name.replace('_', ' ')}
                            </span>
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-slate-600 font-bold">{span.duration_ms.toFixed(1)} ms</span>
                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${
                                span.status === 'ok' ? 'bg-emerald-50 text-emerald-700' :
                                span.status === 'timeout' ? 'bg-amber-50 text-amber-700' : 'bg-rose-50 text-rose-700'
                              }`}>
                                {span.status}
                              </span>
                            </div>
                          </div>
                          {/* Waterfall Bar */}
                          <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden mb-1.5">
                            <div
                              className="h-full bg-indigo-600 rounded-full"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          {span.metadata && Object.keys(span.metadata).length > 0 && (
                            <div className="text-[10px] font-mono text-slate-500 bg-slate-50 p-1.5 rounded">
                              {Object.entries(span.metadata).map(([k, v]) => (
                                <span key={k} className="mr-3">
                                  <span className="text-slate-400">{k}:</span> {String(v)}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 italic">No stage spans captured for this trace.</p>
                )}
              </div>
            </div>

            <div className="px-6 py-3 bg-slate-50 border-t border-slate-200 flex justify-end">
              <button
                onClick={() => setSelectedTrace(null)}
                className="px-4 py-1.5 rounded-lg bg-slate-200 hover:bg-slate-300 text-slate-800 text-xs font-semibold cursor-pointer"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
