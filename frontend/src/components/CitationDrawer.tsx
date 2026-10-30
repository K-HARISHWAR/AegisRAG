import React from 'react';
import { X, FileText, CheckCircle2, Hash, Layers } from 'lucide-react';
import { Citation, RetrievedChunk } from '../types';

interface CitationDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  citations: Citation[];
  retrievedChunks?: RetrievedChunk[];
  queryText?: string;
}

export const CitationDrawer: React.FC<CitationDrawerProps> = ({
  isOpen,
  onClose,
  citations,
  retrievedChunks = [],
  queryText,
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
                      <div className="font-medium text-slate-800 text-sm flex items-center gap-1.5">
                        <FileText size={15} className="text-slate-500 shrink-0" />
                        <span className="truncate" title={cite.document_title}>
                          {cite.document_title}
                        </span>
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
