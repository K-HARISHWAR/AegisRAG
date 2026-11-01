import React from 'react';
import { X, FileText, CheckCircle2, Hash, Layers, ShieldCheck, AlertTriangle, CheckCheck } from 'lucide-react';
import { Citation, EvidenceDiagnostics, RetrievedChunk } from '../types';

interface CitationDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  citations: Citation[];
  retrievedChunks?: RetrievedChunk[];
  queryText?: string;
  evidenceDiagnostics?: EvidenceDiagnostics | null;
  evidenceLevel?: string;
}

export const CitationDrawer: React.FC<CitationDrawerProps> = ({
  isOpen,
  onClose,
  citations,
  retrievedChunks = [],
  queryText,
  evidenceDiagnostics,
  evidenceLevel,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/40 backdrop-blur-xs flex justify-end animate-fadeIn">
      <div className="w-full max-w-lg bg-white h-full shadow-2xl flex flex-col border-l border-slate-200">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div>
            <h2 className="text-base font-semibold text-slate-800 flex items-center gap-2">
              <FileText size={18} className="text-indigo-600" />
              Grounded Evidence & Citations
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Verified against PostgreSQL RBAC source of truth
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 transition-colors cursor-pointer"
            aria-label="Close citations drawer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {queryText && (
            <div className="p-3 bg-indigo-50/60 rounded-lg border border-indigo-100 text-xs text-indigo-900">
              <span className="font-semibold text-indigo-700">Question: </span>
              {queryText}
            </div>
          )}

          {/* Qualitative Evidence Validation & Faithfulness Card */}
          {(evidenceLevel || evidenceDiagnostics) && (
            <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/70 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                  <ShieldCheck size={14} className="text-indigo-600" />
                  Evidence Grounding Diagnostics
                </span>
                {evidenceLevel && (
                  <span
                    className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${
                      evidenceLevel === 'strong'
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : evidenceLevel === 'limited'
                        ? 'bg-amber-50 text-amber-700 border-amber-200'
                        : 'bg-rose-50 text-rose-700 border-rose-200'
                    }`}
                  >
                    {evidenceLevel === 'strong' ? (
                      <CheckCircle2 size={11} />
                    ) : (
                      <AlertTriangle size={11} />
                    )}
                    {evidenceLevel.toUpperCase()} EVIDENCE
                  </span>
                )}
              </div>

              {evidenceDiagnostics && (
                <div className="grid grid-cols-2 gap-2 pt-1 text-xs">
                  <div className="p-2.5 rounded-lg bg-white border border-slate-200">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block mb-0.5">
                      Retrieval Relevance
                    </span>
                    <span
                      className={`font-semibold capitalize ${
                        evidenceDiagnostics.retrieval_relevance === 'high'
                          ? 'text-emerald-600'
                          : evidenceDiagnostics.retrieval_relevance === 'medium'
                          ? 'text-amber-600'
                          : 'text-rose-600'
                      }`}
                    >
                      {evidenceDiagnostics.retrieval_relevance}
                    </span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-white border border-slate-200">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block mb-0.5">
                      Claim Faithfulness
                    </span>
                    <span className="font-semibold text-slate-700">
                      {(evidenceDiagnostics.faithfulness_score * 100).toFixed(0)}% (
                      {evidenceDiagnostics.supported_claims_count}/{evidenceDiagnostics.total_claims_count})
                    </span>
                  </div>

                  <div className="col-span-2 p-2.5 rounded-lg bg-white border border-slate-200 flex items-center justify-between">
                    <span className="text-slate-600 flex items-center gap-1">
                      <CheckCheck size={12} className="text-emerald-500" />
                      Citation & Access Integrity
                    </span>
                    <span className="font-semibold text-emerald-600 text-[11px]">
                      {evidenceDiagnostics.citation_integrity_verified ? 'Server Verified' : 'Unverified'}
                    </span>
                  </div>
                </div>
              )}

              {evidenceDiagnostics?.conflicts_detected && (
                <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-[11px] flex items-center gap-1.5">
                  <AlertTriangle size={13} className="shrink-0 text-amber-600" />
                  <span>Conflicting guidance detected across retrieved policy passages.</span>
                </div>
              )}

              {evidenceDiagnostics?.unsupported_claims &&
                evidenceDiagnostics.unsupported_claims.length > 0 && (
                  <div className="pt-2 border-t border-slate-200 text-[11px]">
                    <span className="font-semibold text-rose-600 block mb-1">
                      Unsupported Claims Detected ({evidenceDiagnostics.unsupported_claims.length}):
                    </span>
                    <ul className="list-disc list-inside space-y-1 text-slate-600">
                      {evidenceDiagnostics.unsupported_claims.map((claim, cIdx) => (
                        <li key={cIdx} className="line-clamp-2">
                          {claim}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
            </div>
          )}

          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
              <CheckCircle2 size={14} className="text-emerald-500" />
              Verified Citations ({citations.length})
            </h3>

            {citations.length === 0 ? (
              <p className="text-sm text-slate-500 italic">No citations available for this answer.</p>
            ) : (
              <div className="space-y-4">
                {citations.map((cite, idx) => (
                  <div
                    key={`${cite.document_id}-${idx}`}
                    className="p-4 rounded-lg border border-slate-200 bg-white hover:border-indigo-300 transition-all shadow-xs"
                  >
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="font-medium text-slate-800 text-sm flex items-center gap-1.5 flex-wrap">
                        <FileText size={15} className="text-slate-500 shrink-0" />
                        <span className="truncate max-w-[200px]" title={cite.document_title}>
                          {cite.document_title}
                        </span>
                        {cite.document_version && (
                          <span className="px-1.5 py-0.5 text-[10px] font-mono font-bold rounded bg-slate-100 text-slate-700 border border-slate-300">
                            v{cite.document_version}
                          </span>
                        )}
                      </div>
                      <span className="shrink-0 px-2 py-0.5 text-xs font-semibold rounded bg-indigo-100 text-indigo-700">
                        {cite.location}
                      </span>
                    </div>

                    <blockquote className="text-xs text-slate-600 bg-slate-50 p-3 rounded border-l-3 border-indigo-400 italic mb-2 leading-relaxed">
                      "{cite.snippet}"
                    </blockquote>

                    <div className="flex items-center gap-2 pt-2 border-t border-slate-100 text-[11px] text-slate-400 font-mono">
                      <Hash size={12} className="shrink-0" />
                      <span className="truncate" title={`SHA-256: ${cite.content_hash}`}>
                        Hash: {cite.content_hash.slice(0, 16)}...
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Context Chunks with RRF Ranking Scores */}
          {retrievedChunks.length > 0 && (
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
                <Layers size={14} className="text-indigo-500" />
                Retrieval Passage Diagnostics ({retrievedChunks.length})
              </h3>
              <div className="space-y-3">
                {retrievedChunks.map((chunk, idx) => (
                  <div
                    key={chunk.chunk_id || idx}
                    className="p-3 rounded-lg border border-slate-100 bg-slate-50/50 text-xs"
                  >
                    <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1.5 font-medium">
                      <span>{chunk.document_title} ({chunk.location})</span>
                      <span className="text-indigo-600 font-mono">
                        RRF: {chunk.combined_score?.toFixed(4) || 'N/A'}
                      </span>
                    </div>
                    <p className="text-slate-600 line-clamp-3 leading-relaxed">
                      {chunk.text}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-200 bg-slate-50 text-right">
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

