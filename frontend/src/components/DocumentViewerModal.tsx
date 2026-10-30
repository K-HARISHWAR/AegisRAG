import React, { useEffect, useState } from 'react';
import { X, FileText, Shield, UserPlus, Lock } from 'lucide-react';
import { api } from '../api/client';
import { DocumentContentResponse, DocumentItem } from '../types';
import { useAuth } from '../auth/AuthContext';

interface DocumentViewerModalProps {
  document: DocumentItem | null;
  onClose: () => void;
  onOpenGrantModal: (doc: DocumentItem) => void;
}

export const DocumentViewerModal: React.FC<DocumentViewerModalProps> = ({
  document,
  onClose,
  onOpenGrantModal,
}) => {
  const { isManager, isAdmin } = useAuth();
  const [content, setContent] = useState<DocumentContentResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'passages' | 'grants'>('passages');

  useEffect(() => {
    if (!document) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

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

  if (!document) return null;

  const canManageGrants = isAdmin || isManager;

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
              <div className="flex items-center gap-2">
                <h3 className="text-base font-semibold text-slate-800">{document.title}</h3>
                {document.is_confidential && (
                  <span className="px-2 py-0.5 text-[10px] font-semibold bg-amber-100 text-amber-800 rounded flex items-center gap-1">
                    <Lock size={10} /> Confidential
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 font-mono">
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
                {canManageGrants && (
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
