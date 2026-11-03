import React, { useEffect, useState } from 'react';
import {
  X,
  FileSearch,
  AlertTriangle,
  CheckCircle,
  FileText,
  Table as TableIcon,
  ScanText,
  Layers,
} from 'lucide-react';
import { api } from '../api/client';
import { DocumentExtractionPreviewResponse, DocumentItem } from '../types';

interface ExtractionPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  document?: DocumentItem | null;
  previewData?: DocumentExtractionPreviewResponse | null;
}

export const ExtractionPreviewModal: React.FC<ExtractionPreviewModalProps> = ({
  isOpen,
  onClose,
  document,
  previewData: initialPreviewData,
}) => {
  const [data, setData] = useState<DocumentExtractionPreviewResponse | null>(initialPreviewData || null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    if (initialPreviewData) {
      setData(initialPreviewData);
      setLoading(false);
      setError(null);
      return;
    }

    if (document) {
      setLoading(true);
      setError(null);
      api.documents
        .getExtractionPreview(document.id)
        .then((res) => {
          setData(res);
          setLoading(false);
        })
        .catch((err: any) => {
          setError(err?.message || 'Failed to fetch extraction preview and quality telemetry');
          setLoading(false);
        });
    }
  }, [isOpen, document, initialPreviewData]);

  if (!isOpen) return null;

  const qualityScore = data?.quality_report?.quality_score ?? 1.0;
  const scorePercent = Math.round(qualityScore * 100);

  const getScoreBadgeClass = (score: number) => {
    if (score >= 85) return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    if (score >= 60) return 'bg-amber-50 text-amber-700 border-amber-200';
    return 'bg-red-50 text-red-700 border-red-200';
  };

  const getMethodBadge = (method?: string | null) => {
    switch (method) {
      case 'ocr':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-purple-50 text-purple-700 border border-purple-200">
            <ScanText size={11} /> Scanned OCR
          </span>
        );
      case 'table_aware':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            <TableIcon size={11} /> Table-Aware
          </span>
        );
      case 'spreadsheet_grid':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <Layers size={11} /> Grid Range
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
            <FileText size={11} /> Native Text
          </span>
        );
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-3xl w-full border border-slate-200 overflow-hidden flex flex-col max-h-[90vh] animate-scaleIn">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-indigo-50 text-indigo-600">
              <FileSearch size={20} />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-base font-semibold text-slate-800">
                  {data?.title || document?.title || 'Document Extraction Preview'}
                </h3>
                {data && (
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${getScoreBadgeClass(
                      scorePercent
                    )}`}
                  >
                    Quality Score: {scorePercent}%
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 font-mono mt-0.5">
                Format: {(data?.file_type || document?.file_type || 'Unknown').toUpperCase()} • Telemetry & Provenance Analysis
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

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {loading && (
            <div className="py-16 text-center text-slate-400 text-xs">
              <span className="inline-block w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mb-2" />
              <p>Extracting document intelligence, tables, and OCR telemetry...</p>
            </div>
          )}

          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-center gap-2">
              <AlertTriangle size={16} className="text-red-500 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {!loading && !error && data && (
            <>
              {/* Warnings Banner */}
              {data.quality_report.warnings && data.quality_report.warnings.length > 0 && (
                <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900 space-y-1">
                  <div className="flex items-center gap-2 font-semibold">
                    <AlertTriangle size={15} className="text-amber-600 shrink-0" />
                    <span>Extraction Warnings Detected ({data.quality_report.warnings.length})</span>
                  </div>
                  <ul className="list-disc list-inside pl-1 text-[11px] text-amber-800 space-y-0.5">
                    {data.quality_report.warnings.map((w, idx) => (
                      <li key={idx}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Telemetry Metrics Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                  <div className="text-[10px] font-semibold text-slate-500 uppercase">Pages / Sheets</div>
                  <div className="text-base font-bold text-slate-800 mt-1">
                    {data.quality_report.pages_processed}
                  </div>
                  <div className="text-[10px] text-slate-400 mt-0.5">
                    {data.quality_report.native_text_pages} native • {data.quality_report.ocr_pages} OCR
                  </div>
                </div>

                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                  <div className="text-[10px] font-semibold text-slate-500 uppercase">Total Characters</div>
                  <div className="text-base font-bold text-slate-800 mt-1">
                    {data.quality_report.total_characters.toLocaleString()}
                  </div>
                  <div className="text-[10px] text-slate-400 mt-0.5">
                    {data.total_passages} total passages
                  </div>
                </div>

                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                  <div className="text-[10px] font-semibold text-slate-500 uppercase">Tables & Grids</div>
                  <div className="text-base font-bold text-slate-800 mt-1 flex items-center gap-1.5">
                    {data.quality_report.has_tables ? (
                      <span className="text-blue-600 flex items-center gap-1 text-sm font-semibold">
                        <CheckCircle size={14} /> Detected
                      </span>
                    ) : (
                      <span className="text-slate-400 text-sm font-normal">None</span>
                    )}
                  </div>
                  <div className="text-[10px] text-slate-400 mt-0.5">Header-paired</div>
                </div>

                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                  <div className="text-[10px] font-semibold text-slate-500 uppercase">OCR Processing</div>
                  <div className="text-base font-bold text-slate-800 mt-1 flex items-center gap-1.5">
                    {data.quality_report.has_ocr ? (
                      <span className="text-purple-600 flex items-center gap-1 text-sm font-semibold">
                        <ScanText size={14} /> Active
                      </span>
                    ) : (
                      <span className="text-emerald-600 text-sm font-semibold flex items-center gap-1">
                        <CheckCircle size={14} /> Digital Native
                      </span>
                    )}
                  </div>
                  <div className="text-[10px] text-slate-400 mt-0.5">Zero duplications</div>
                </div>
              </div>

              {/* Passages List with Provenance & Extraction Method */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">
                    Extracted Content & Coordinate Provenance
                  </h4>
                  <span className="text-[11px] text-slate-400">
                    {data.passages.length} passages shown
                  </span>
                </div>

                <div className="space-y-3">
                  {data.passages.map((p, idx) => (
                    <div
                      key={idx}
                      className="p-3.5 bg-slate-50/80 rounded-lg border border-slate-200 text-xs hover:border-slate-300 transition-colors"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2 mb-2 pb-2 border-b border-slate-200/60">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-indigo-700 bg-indigo-50 border border-indigo-100 px-2 py-0.5 rounded text-[11px]">
                            {p.location}
                          </span>
                          {getMethodBadge(p.extraction_method)}
                        </div>
                        <div className="flex items-center gap-2 text-[10px] font-mono text-slate-400">
                          {p.confidence !== undefined && p.confidence !== null && (
                            <span>Confidence: {Math.round(p.confidence * 100)}%</span>
                          )}
                          <span>Passage #{p.index}</span>
                        </div>
                      </div>
                      <p className="text-slate-800 whitespace-pre-wrap leading-relaxed font-sans text-xs">
                        {p.text}
                      </p>
                    </div>
                  ))}

                  {data.passages.length === 0 && (
                    <div className="text-center py-8 border border-dashed border-slate-200 rounded-lg text-slate-400 text-xs">
                      No extractable text found in this file.
                    </div>
                  )}
                </div>
              </div>
            </>
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