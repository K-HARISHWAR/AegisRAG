import React, { useEffect, useState } from 'react';
import { X, FileText, Shield, UserPlus, Lock, History, RotateCcw, CheckCircle2 } from 'lucide-react';
import { api } from '../api/client';
import { DocumentContentResponse, DocumentHistoryResponse, DocumentItem } from '../types';
import { useAuth } from '../auth/AuthContext';

interface DocumentViewerModalProps {
  document: DocumentItem | null;
  onClose: () => void;
  onOpenGrantModal: (doc: DocumentItem) => void;
  onDocumentUpdated?: () => void;
}

export const DocumentViewerModal: React.FC<DocumentViewerModalProps> = ({
  document,
  onClose,
  onOpenGrantModal,
  onDocumentUpdated,
}) => {
  const { isManager, isAdmin } = useAuth();
  const [content, setContent] = useState<DocumentContentResponse | null>(null);
  const [history, setHistory] = useState<DocumentHistoryResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingHistory, setLoadingHistory] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [rollbackSuccess, setRollbackSuccess] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'passages' | 'grants' | 'history'>('passages');

  useEffect(() => {
    if (!document) return;

    let isMounted = true;
    setLoading(true);
    setError(null);
    setRollbackSuccess(null);

    api.documents
      .getContent(document.id)
      .then((data) => {
        if (isMounted) {
          setContent(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err?.message || 'Failed to fetch extracted document passages');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [document]);

  const loadHistory = () => {
    if (!document) return;
    setLoadingHistory(true);
    setHistoryError(null);
    api.documents
      .getHistory(document.id)
      .then((data) => {
        setHistory(data);
        setLoadingHistory(false);
      })
      .catch((err) => {
        setHistoryError(err?.message || 'Failed to load document revision history');
        setLoadingHistory(false);
      });
  };

  useEffect(() => {
    if (activeTab === 'history') {
      loadHistory();
    }
  }, [activeTab, document]);

  const handleRollback = async (revisionId: string, version: number) => {
    if (!window.confirm(`Are you sure you want to roll back to revision v${version}? This will make v${version} active and supersede newer versions.`)) {
      return;
    }

    try {
      await api.documents.rollback(revisionId);
      setRollbackSuccess(`Successfully rolled back to revision v${version}.`);
      loadHistory();
      if (onDocumentUpdated) {
        onDocumentUpdated();
      }
    } catch (err: any) {
      setHistoryError(err?.message || 'Failed to execute document rollback');
    }
  };

  if (!document) return null;

  const canManage = isAdmin || isManager;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full border border-slate-200 overflow-hidden flex flex-col max-h-[85vh] animate-scaleIn">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-indigo-50 text-indigo-600">
              <FileText size={20} />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-base font-semibold text-slate-800">{document.title}</h3>
                <span className="px-1.5 py-0.5 text-[10px] font-mono font-bold bg-indigo-100 text-indigo-700 rounded border border-indigo-200">
                  v{document.version}
                </span>
                <span
                  className={`px-2 py-0.5 text-[10px] font-semibold uppercase rounded ${
                    document.lifecycle_state === 'superseded'
                      ? 'bg-amber-100 text-amber-800'
                      : document.lifecycle_state === 'archived'
                      ? 'bg-purple-100 text-purple-800'
                      : 'bg-emerald-100 text-emerald-800'
                  }`}
                >
                  {document.lifecycle_state || 'active'}
                </span>
                {document.is_confidential && (
                  <span className="px-2 py-0.5 text-[10px] font-semibold bg-amber-100 text-amber-800 rounded flex items-center gap-1">
                    <Lock size={10} /> Confidential
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 font-mono mt-0.5">
                {document.file_type.toUpperCase()} • {(document.file_size_bytes / 1024).toFixed(1)} KB •
                SHA-256: {document.checksum_sha256.slice(0, 12)}...
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 transition-colors cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="px-6 border-b border-slate-200 bg-white flex gap-6 text-xs font-semibold">
          <button
            onClick={() => setActiveTab('passages')}
            className={`py-3 border-b-2 transition-colors cursor-pointer ${
              activeTab === 'passages'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            Extracted Passages ({content?.total_passages || 0})
          </button>
          <button
            onClick={() => setActiveTab('grants')}
            className={`py-3 border-b-2 transition-colors cursor-pointer ${
              activeTab === 'grants'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            Access Grants ({document.grants?.length || 0})
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`py-3 border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 ${
              activeTab === 'history'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <History size={14} />
            Revision Timeline
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {activeTab === 'passages' && (
            <>
              {loading && (
                <div className="py-12 text-center text-slate-400 text-xs">
                  <span className="inline-block w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mb-2" />
                  <p>Loading document passages and provenance coordinates...</p>
                </div>
              )}

              {error && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                  {error}
                </div>
              )}

              {!loading && !error && content && (
                <div className="space-y-3">
                  {content.passages.map((p, idx) => (
                    <div
                      key={idx}
                      className="p-3.5 bg-slate-50/70 rounded-lg border border-slate-200/80 text-xs"
                    >
                      <div className="flex items-center justify-between text-[11px] font-semibold text-indigo-700 mb-1.5">
                        <span className="px-1.5 py-0.5 bg-indigo-50 border border-indigo-100 rounded">
                          {p.location}
                        </span>
                        <span className="text-slate-400 font-mono">Passage #{p.index}</span>
                      </div>
                      <p className="text-slate-700 whitespace-pre-wrap leading-relaxed">{p.text}</p>
                    </div>
                  ))}
                  {content.passages.length === 0 && (
                    <p className="text-slate-400 text-xs text-center py-8">
                      No text passages could be extracted from this document.
                    </p>
                  )}
                </div>
              )}
            </>
          )}

          {activeTab === 'grants' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                    Explicit Access Grants
                  </h4>
                  <p className="text-xs text-slate-400">
                    Overrides department isolation for specific users or roles.
                  </p>
                </div>
                {canManage && (
                  <button
                    onClick={() => onOpenGrantModal(document)}
                    className="px-3 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg flex items-center gap-1.5 cursor-pointer shadow-xs"
                  >
                    <UserPlus size={14} /> Add Grant
                  </button>
                )}
              </div>

              {document.grants && document.grants.length > 0 ? (
                <div className="space-y-2">
                  {document.grants.map((grant) => (
                    <div
                      key={grant.id}
                      className="p-3 rounded-lg border border-slate-200 bg-slate-50 flex items-center justify-between text-xs"
                    >
                      <div>
                        <div className="font-semibold text-slate-800">
                          {grant.grantee_user_id
                            ? `User: ${grant.grantee_user_id}`
                            : `Role: ${grant.grantee_role_id}`}
                        </div>
                        <div className="text-[11px] text-slate-400">
                          Granted on {new Date(grant.created_at).toLocaleDateString()}
                        </div>
                      </div>
                      <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-semibold text-[11px]">
                        {grant.permission.toUpperCase()}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 border border-dashed border-slate-200 rounded-lg text-slate-400 text-xs">
                  <Shield size={24} className="mx-auto mb-1 text-slate-300" />
                  <p>No explicit grants assigned.</p>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Access is governed by department assignment and confidentiality policy.
                  </p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'history' && (
            <div className="space-y-4">
              {rollbackSuccess && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 flex items-center gap-2">
                  <CheckCircle2 size={16} className="text-emerald-500 shrink-0" />
                  <span>{rollbackSuccess}</span>
                </div>
              )}

              {historyError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                  {historyError}
                </div>
              )}

              {loadingHistory && (
                <div className="py-12 text-center text-slate-400 text-xs">
                  <span className="inline-block w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mb-2" />
                  <p>Loading revision timeline...</p>
                </div>
              )}

              {!loadingHistory && history && (
                <div className="space-y-3">
                  <div className="text-xs text-slate-500 mb-2">
                    <span className="font-semibold text-slate-700">{history.total_revisions} total revisions</span> for this document family.
                  </div>
                  {history.revisions.map((rev) => {
                    const isActive = rev.lifecycle_state === 'active';
                    return (
                      <div
                        key={rev.id}
                        className={`p-3.5 rounded-lg border text-xs transition-all ${
                          isActive
                            ? 'bg-emerald-50/40 border-emerald-300 shadow-xs'
                            : 'bg-slate-50/70 border-slate-200'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="px-2 py-0.5 text-xs font-mono font-bold rounded bg-indigo-100 text-indigo-700">
                              v{rev.version}
                            </span>
                            <span
                              className={`px-2 py-0.5 text-[10px] font-semibold uppercase rounded ${
                                isActive
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : 'bg-slate-200 text-slate-700'
                              }`}
                            >
                              {rev.lifecycle_state}
                            </span>
                          </div>

                          {canManage && !isActive && rev.lifecycle_state !== 'deleted' && (
                            <button
                              onClick={() => handleRollback(rev.id, rev.version)}
                              className="px-2.5 py-1 text-[11px] font-semibold text-indigo-600 bg-white border border-indigo-200 hover:bg-indigo-50 rounded-md flex items-center gap-1 cursor-pointer transition-colors shadow-2xs"
                              title={`Roll back to make v${rev.version} the active document version`}
                            >
                              <RotateCcw size={12} />
                              Rollback to v{rev.version}
                            </button>
                          )}
                        </div>

                        <div className="text-[11px] text-slate-500 space-y-1">
                          <div>
                            Uploaded on <span className="font-medium text-slate-700">{new Date(rev.created_at).toLocaleString()}</span>
                          </div>
                          <div className="font-mono text-[10px] text-slate-400">
                            SHA-256: {rev.checksum_sha256.slice(0, 20)}... • {(rev.file_size_bytes / 1024).toFixed(1)} KB
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-200 bg-slate-50 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
