import React, { useState, useEffect } from 'react';
import {
  GitCompare,
  FileText,
  Layers,
  ShieldCheck,
  Download,
  Clock,
  CheckCircle2,
  AlertTriangle,
  FileCheck,
  ChevronRight,
  RefreshCw,
} from 'lucide-react';
import { api } from '../api/client';
import {
  DocumentItem,
  VersionComparisonResponse,
  CollectionSummaryResponse,
  StructuredExtractionResponse,
  WorkflowExecutionRead,
  ToolAllowlistInfo,
} from '../types';

export const WorkflowsPage: React.FC = () => {
  const [activeWorkflowTab, setActiveWorkflowTab] = useState<'compare' | 'summary' | 'extract' | 'history'>('compare');
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoadingDocs, setIsLoadingDocs] = useState<boolean>(true);
  const [toolAllowlist, setToolAllowlist] = useState<ToolAllowlistInfo | null>(null);

  // --- Version Comparison State ---
  const [sourceDocId, setSourceDocId] = useState<string>('');
  const [targetDocId, setTargetDocId] = useState<string>('');
  const [comparisonFocus, setComparisonFocus] = useState<string>('');
  const [comparisonResult, setComparisonResult] = useState<VersionComparisonResponse | null>(null);
  const [isComparing, setIsComparing] = useState<boolean>(false);
  const [compareError, setCompareError] = useState<string | null>(null);

  // --- Collection Summary State ---
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [collectionTitle, setCollectionTitle] = useState<string>('Quarterly Policy & Runbook Collection');
  const [summaryResult, setSummaryResult] = useState<CollectionSummaryResponse | null>(null);
  const [isSummarizing, setIsSummarizing] = useState<boolean>(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  // --- Structured Extraction State ---
  const [extractionDocId, setExtractionDocId] = useState<string>('');
  const [extractionTemplate, setExtractionTemplate] = useState<string>('policy');
  const [extractionResult, setExtractionResult] = useState<StructuredExtractionResponse | null>(null);
  const [isExtracting, setIsExtracting] = useState<boolean>(false);
  const [extractionError, setExtractionError] = useState<string | null>(null);

  // --- Workflow History State ---
  const [workflowHistory, setWorkflowHistory] = useState<WorkflowExecutionRead[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(false);

  // Export progress
  const [isExporting, setIsExporting] = useState<boolean>(false);

  useEffect(() => {
    loadDocuments();
    loadToolAllowlist();
  }, []);

  useEffect(() => {
    if (activeWorkflowTab === 'history') {
      loadHistory();
    }
  }, [activeWorkflowTab]);

  const loadDocuments = async () => {
    try {
      setIsLoadingDocs(true);
      const docs = await api.documents.list(true); // include revisions
      setDocuments(docs);
      if (docs.length > 0) {
        setSourceDocId(docs[0].id);
        if (docs.length > 1) {
          setTargetDocId(docs[1].id);
        } else {
          setTargetDocId(docs[0].id);
        }
        setExtractionDocId(docs[0].id);
        setSelectedDocIds(docs.slice(0, 3).map((d) => d.id));
      }
    } catch (err) {
      console.error('Failed to load documents for workflows:', err);
    } finally {
      setIsLoadingDocs(false);
    }
  };

  const loadToolAllowlist = async () => {
    try {
      const tools = await api.workflows.getTools();
      setToolAllowlist(tools);
    } catch (err) {
      console.error('Failed to load tool allowlist:', err);
    }
  };

  const loadHistory = async () => {
    try {
      setIsLoadingHistory(true);
      const history = await api.workflows.getHistory(30);
      setWorkflowHistory(history);
    } catch (err) {
      console.error('Failed to load workflow history:', err);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  // --- Execute Handlers ---

  const handleRunComparison = async () => {
    if (!sourceDocId || !targetDocId) return;
    try {
      setIsComparing(true);
      setCompareError(null);
      setComparisonResult(null);
      const res = await api.workflows.compare({
        source_document_id: sourceDocId,
        target_document_id: targetDocId,
        focus: comparisonFocus.trim() || undefined,
      });
      setComparisonResult(res);
    } catch (err: any) {
      setCompareError(err.message || 'Comparison failed. Access may be denied by PostgreSQL policy.');
    } finally {
      setIsComparing(false);
    }
  };

  const handleRunSummary = async () => {
    if (selectedDocIds.length === 0) return;
    try {
      setIsSummarizing(true);
      setSummaryError(null);
      setSummaryResult(null);
      const res = await api.workflows.summarizeCollection({
        document_ids: selectedDocIds,
        collection_title: collectionTitle.trim() || undefined,
      });
      setSummaryResult(res);
    } catch (err: any) {
      setSummaryError(err.message || 'Collection summary failed. Restricted files may have failed closed.');
    } finally {
      setIsSummarizing(false);
    }
  };

  const handleRunExtraction = async () => {
    if (!extractionDocId) return;
    try {
      setIsExtracting(true);
      setExtractionError(null);
      setExtractionResult(null);
      const res = await api.workflows.extractFields({
        document_id: extractionDocId,
        template_type: extractionTemplate,
      });
      setExtractionResult(res);
    } catch (err: any) {
      setExtractionError(err.message || 'Field extraction failed.');
    } finally {
      setIsExtracting(false);
    }
  };

  const handleExport = async (type: string, data: any, format: 'markdown' | 'pdf', title: string) => {
    try {
      setIsExporting(true);
      const blob = await api.workflows.exportWorkflow({
        workflow_type: type,
        data,
        format,
        title,
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${title.toLowerCase().replace(/[^\w]/g, '_')}.${format === 'pdf' ? 'pdf' : 'md'}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      alert(`Export failed: ${err.message}`);
    } finally {
      setIsExporting(false);
    }
  };

  const toggleDocSelection = (id: string) => {
    if (selectedDocIds.includes(id)) {
      setSelectedDocIds(selectedDocIds.filter((item) => item !== id));
    } else {
      setSelectedDocIds([...selectedDocIds, id]);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Top Header & Tool Allowlist Guardrail Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-slate-200 gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 rounded-lg bg-indigo-50 text-indigo-600">
              <Layers size={22} />
            </span>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Read-Only Knowledge Workflows</h1>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Server-verified multi-step workflows with strict tool allowlists, dual-version citations, and default-deny RBAC.
          </p>
        </div>

        {/* Security Guardrail Pill */}
        <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-200 text-emerald-800 px-3 py-2 rounded-lg text-xs font-medium">
          <ShieldCheck size={16} className="text-emerald-600 shrink-0" />
          <div>
            <div className="font-semibold text-emerald-900">Approved Tool Allowlist Active</div>
            <div className="text-[10px] text-emerald-700">
              {toolAllowlist?.allowed_tools.length || 4} Read-Only Tools • Shell/SQL/Writes Blocked
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="flex items-center gap-2 mt-6 border-b border-slate-200 pb-2">
        <button
          onClick={() => setActiveWorkflowTab('compare')}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
            activeWorkflowTab === 'compare'
              ? 'bg-indigo-600 text-white shadow-xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          <GitCompare size={15} />
          <span>Version Comparison</span>
        </button>

        <button
          onClick={() => setActiveWorkflowTab('summary')}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
            activeWorkflowTab === 'summary'
              ? 'bg-indigo-600 text-white shadow-xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          <FileText size={15} />
          <span>Collection Summary</span>
        </button>

        <button
          onClick={() => setActiveWorkflowTab('extract')}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
            activeWorkflowTab === 'extract'
              ? 'bg-indigo-600 text-white shadow-xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          <FileCheck size={15} />
          <span>Structured Extraction</span>
        </button>

        <button
          onClick={() => setActiveWorkflowTab('history')}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
            activeWorkflowTab === 'history'
              ? 'bg-indigo-600 text-white shadow-xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          <Clock size={15} />
          <span>Execution History</span>
        </button>
      </div>

      {/* ============================================================== */}
      {/* 1. VERSION COMPARISON TAB                                      */}
      {/* ============================================================== */}
      {activeWorkflowTab === 'compare' && (
        <div className="mt-6 space-y-6">
          {/* Configuration Card */}
          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs">
            <h2 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <GitCompare size={16} className="text-indigo-600" />
              <span>Compare Two Document Versions & Policy Deltas</span>
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Select a baseline version (v1) and target version (v2). Both revisions are revalidated against PostgreSQL permissions before diff analysis.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Baseline Document / Version A</label>
                <select
                  value={sourceDocId}
                  onChange={(e) => setSourceDocId(e.target.value)}
                  disabled={isLoadingDocs}
                  className="w-full text-xs border border-slate-300 rounded-lg p-2.5 bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  {documents.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.title} (v{doc.version}) • {doc.lifecycle_state || 'active'} • {doc.id.slice(0, 8)}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Target Document / Version B</label>
                <select
                  value={targetDocId}
                  onChange={(e) => setTargetDocId(e.target.value)}
                  disabled={isLoadingDocs}
                  className="w-full text-xs border border-slate-300 rounded-lg p-2.5 bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  {documents.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.title} (v{doc.version}) • {doc.lifecycle_state || 'active'} • {doc.id.slice(0, 8)}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="mt-4">
              <label className="block text-xs font-medium text-slate-700 mb-1">Comparison Focus (Optional)</label>
              <input
                type="text"
                placeholder="e.g., SLA timelines, remote work stipend, security rotations"
                value={comparisonFocus}
                onChange={(e) => setComparisonFocus(e.target.value)}
                className="w-full text-xs border border-slate-300 rounded-lg p-2.5 bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="mt-5 flex items-center justify-between">
              <button
                onClick={handleRunComparison}
                disabled={isComparing || isLoadingDocs || !sourceDocId || !targetDocId}
                className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-all shadow-xs cursor-pointer"
              >
                {isComparing ? (
                  <>
                    <RefreshCw size={14} className="animate-spin" />
                    <span>Executing Fixed Workflow Steps...</span>
                  </>
                ) : (
                  <>
                    <GitCompare size={14} />
                    <span>Run Version Comparison</span>
                  </>
                )}
              </button>

              <span className="text-[11px] text-slate-400">
                Tool Allowlist: <code className="bg-slate-100 px-1 py-0.5 rounded text-slate-600">compare_document_versions</code>
              </span>
            </div>

            {compareError && (
              <div className="mt-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-xs flex items-center gap-2">
                <AlertTriangle size={16} className="shrink-0 text-red-500" />
                <span>{compareError}</span>
              </div>
            )}
          </div>

          {/* Result View */}
          {comparisonResult && (
            <div className="space-y-6">
              {/* Telemetry & Action Bar */}
              <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center gap-4 text-xs text-slate-600">
                  <div className="flex items-center gap-1.5 font-medium">
                    <CheckCircle2 size={16} className="text-emerald-500" />
                    <span>Execution Completed ({comparisonResult.total_duration_ms} ms)</span>
                  </div>
                  <div className="h-4 w-px bg-slate-200" />
                  <span className="bg-emerald-50 text-emerald-700 font-semibold px-2 py-0.5 rounded text-[11px]">
                    +{comparisonResult.total_added} Added
                  </span>
                  <span className="bg-red-50 text-red-700 font-semibold px-2 py-0.5 rounded text-[11px]">
                    -{comparisonResult.total_removed} Removed
                  </span>
                  <span className="bg-amber-50 text-amber-700 font-semibold px-2 py-0.5 rounded text-[11px]">
                    ~{comparisonResult.total_modified} Modified
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleExport('compare', comparisonResult, 'markdown', 'Version_Comparison_Report')}
                    disabled={isExporting}
                    className="flex items-center gap-1.5 px-3 py-1.5 border border-slate-300 rounded-lg text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
                  >
                    <Download size={13} />
                    <span>Export MD</span>
                  </button>

                  <button
                    onClick={() => handleExport('compare', comparisonResult, 'pdf', 'Version_Comparison_Report')}
                    disabled={isExporting}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-medium transition-colors cursor-pointer"
                  >
                    <Download size={13} />
                    <span>Export PDF</span>
                  </button>
                </div>
              </div>

              {/* Execution Steps Trace */}
              <div className="bg-slate-900 text-slate-200 rounded-xl p-4 text-xs font-mono">
                <div className="text-slate-400 font-sans font-semibold mb-2 flex items-center gap-2">
                  <Clock size={14} />
                  <span>Workflow Execution Trace (Fixed Tool Steps)</span>
                </div>
                <div className="space-y-1.5">
                  {comparisonResult.steps.map((step, idx) => (
                    <div key={idx} className="flex items-center justify-between border-b border-slate-800 py-1">
                      <span className="text-indigo-400">
                        {idx + 1}. {step.step_name} [{step.tool_name}]
                      </span>
                      <div className="flex items-center gap-3">
                        <span className="text-emerald-400 uppercase text-[10px]">{step.status}</span>
                        <span className="text-slate-500 text-[10px]">{step.duration_ms}ms</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Clause-by-Clause Differences */}
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs">
                <h3 className="text-sm font-semibold text-slate-900 mb-2">Clause-by-Clause Comparison & Policy Impact</h3>
                <p className="text-xs text-slate-500 mb-4">{comparisonResult.executive_summary}</p>

                <div className="space-y-4">
                  {comparisonResult.diff_items.map((diff, idx) => (
                    <div
                      key={idx}
                      className={`border rounded-xl p-4 text-xs ${
                        diff.clause_type === 'added'
                          ? 'border-emerald-200 bg-emerald-50/40'
                          : diff.clause_type === 'removed'
                          ? 'border-red-200 bg-red-50/40'
                          : 'border-amber-200 bg-amber-50/40'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span
                          className={`uppercase text-[10px] font-bold px-2 py-0.5 rounded ${
                            diff.clause_type === 'added'
                              ? 'bg-emerald-100 text-emerald-800'
                              : diff.clause_type === 'removed'
                              ? 'bg-red-100 text-red-800'
                              : 'bg-amber-100 text-amber-800'
                          }`}
                        >
                          {diff.clause_type} Clause
                        </span>
                        <span className="text-[11px] text-slate-500 italic">{diff.policy_impact}</span>
                      </div>

                      {/* Source vs Target Content */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                        {diff.source_text && (
                          <div className="bg-white border border-slate-200 rounded-lg p-3">
                            <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">
                              Source (v{comparisonResult.source_document.version})
                            </span>
                            <p className="text-slate-800 text-xs">{diff.source_text}</p>
                            {diff.source_citation && (
                              <div className="mt-2 text-[10px] text-indigo-600 font-mono bg-indigo-50 inline-block px-1.5 py-0.5 rounded">
                                {diff.source_citation}
                              </div>
                            )}
                          </div>
                        )}

                        {diff.target_text && (
                          <div className="bg-white border border-slate-200 rounded-lg p-3">
                            <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">
                              Target (v{comparisonResult.target_document.version})
                            </span>
                            <p className="text-slate-800 text-xs">{diff.target_text}</p>
                            {diff.target_citation && (
                              <div className="mt-2 text-[10px] text-indigo-600 font-mono bg-indigo-50 inline-block px-1.5 py-0.5 rounded">
                                {diff.target_citation}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ============================================================== */}
      {/* 2. COLLECTION SUMMARY TAB                                      */}
      {/* ============================================================== */}
      {activeWorkflowTab === 'summary' && (
        <div className="mt-6 space-y-6">
          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs">
            <h2 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <FileText size={16} className="text-indigo-600" />
              <span>Synthesize Authorized Document Collection</span>
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Select documents to synthesize into an executive briefing. Restricted documents are filtered out automatically by server-verified PostgreSQL RBAC.
            </p>

            <div className="mt-4">
              <label className="block text-xs font-medium text-slate-700 mb-1">Collection Title</label>
              <input
                type="text"
                value={collectionTitle}
                onChange={(e) => setCollectionTitle(e.target.value)}
                className="w-full text-xs border border-slate-300 rounded-lg p-2.5 bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="mt-4">
              <label className="block text-xs font-medium text-slate-700 mb-2">Select Accessible Documents</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 max-h-48 overflow-y-auto border border-slate-200 rounded-lg p-3 bg-slate-50">
                {documents.map((doc) => (
                  <label
                    key={doc.id}
                    className={`flex items-start gap-2 p-2 rounded-lg border text-xs cursor-pointer transition-colors ${
                      selectedDocIds.includes(doc.id)
                        ? 'border-indigo-500 bg-indigo-50/60 text-indigo-900'
                        : 'border-slate-200 bg-white hover:bg-slate-100 text-slate-700'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedDocIds.includes(doc.id)}
                      onChange={() => toggleDocSelection(doc.id)}
                      className="mt-0.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="font-medium truncate">{doc.title}</div>
                      <div className="text-[10px] text-slate-400">
                        v{doc.version} • {doc.is_confidential ? 'Confidential' : 'Standard'}
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            <div className="mt-5 flex items-center justify-between">
              <button
                onClick={handleRunSummary}
                disabled={isSummarizing || selectedDocIds.length === 0}
                className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-all shadow-xs cursor-pointer"
              >
                {isSummarizing ? (
                  <>
                    <RefreshCw size={14} className="animate-spin" />
                    <span>Synthesizing Authorized Sources...</span>
                  </>
                ) : (
                  <>
                    <FileText size={14} />
                    <span>Synthesize Collection</span>
                  </>
                )}
              </button>

              <span className="text-[11px] text-slate-400">
                Tool Allowlist: <code className="bg-slate-100 px-1 py-0.5 rounded text-slate-600">summarize_collection</code>
              </span>
            </div>

            {summaryError && (
              <div className="mt-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-xs flex items-center gap-2">
                <AlertTriangle size={16} className="shrink-0 text-red-500" />
                <span>{summaryError}</span>
              </div>
            )}
          </div>

          {/* Collection Summary Result */}
          {summaryResult && (
            <div className="space-y-6">
              <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center gap-4 text-xs text-slate-600">
                  <div className="flex items-center gap-1.5 font-medium">
                    <CheckCircle2 size={16} className="text-emerald-500" />
                    <span>{summaryResult.total_documents_analyzed} Documents Synthesized</span>
                  </div>
                  {summaryResult.excluded_restricted_count > 0 && (
                    <span className="bg-amber-50 text-amber-800 px-2 py-0.5 rounded text-[11px] font-semibold">
                      {summaryResult.excluded_restricted_count} Restricted Excluded
                    </span>
                  )}
                  <span className="text-slate-400 text-[11px]">({summaryResult.total_duration_ms} ms)</span>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleExport('collection_summary', summaryResult, 'markdown', summaryResult.collection_title)}
                    disabled={isExporting}
                    className="flex items-center gap-1.5 px-3 py-1.5 border border-slate-300 rounded-lg text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
                  >
                    <Download size={13} />
                    <span>Export MD</span>
                  </button>

                  <button
                    onClick={() => handleExport('collection_summary', summaryResult, 'pdf', summaryResult.collection_title)}
                    disabled={isExporting}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-medium transition-colors cursor-pointer"
                  >
                    <Download size={13} />
                    <span>Export PDF</span>
                  </button>
                </div>
              </div>

              {/* Thematic Findings */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {summaryResult.thematic_findings.map((finding, idx) => (
                  <div key={idx} className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
                    <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider text-indigo-600 mb-1">
                      {finding.theme}
                    </h4>
                    <p className="text-xs text-slate-600 mb-3">{finding.summary}</p>
                    <ul className="space-y-1.5 text-xs text-slate-700">
                      {finding.points.map((pt, pIdx) => (
                        <li key={pIdx} className="flex items-start gap-1.5">
                          <ChevronRight size={13} className="shrink-0 text-slate-400 mt-0.5" />
                          <span>{pt}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>

              {/* Document Breakdown */}
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs">
                <h3 className="text-sm font-semibold text-slate-900 mb-3">Document Takeaways & Citations</h3>
                <div className="divide-y divide-slate-100">
                  {summaryResult.document_breakdowns.map((doc, idx) => (
                    <div key={idx} className="py-3 first:pt-0 last:pb-0">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-semibold text-xs text-slate-800">
                          {doc.title} (v{doc.version})
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono">{doc.document_id.slice(0, 8)}</span>
                      </div>
                      <ul className="space-y-1 text-xs text-slate-600 pl-3">
                        {doc.key_takeaways.map((t, tIdx) => (
                          <li key={tIdx} className="list-disc">
                            {t}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ============================================================== */}
      {/* 3. STRUCTURED EXTRACTION TAB                                   */}
      {/* ============================================================== */}
      {activeWorkflowTab === 'extract' && (
        <div className="mt-6 space-y-6">
          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs">
            <h2 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <FileCheck size={16} className="text-indigo-600" />
              <span>Extract Structured Metadata, Deadlines, Requirements & Risks</span>
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Extracts typed operational parameters from authorized documents with exact citation coordinates.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Target Document</label>
                <select
                  value={extractionDocId}
                  onChange={(e) => setExtractionDocId(e.target.value)}
                  className="w-full text-xs border border-slate-300 rounded-lg p-2.5 bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  {documents.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.title} (v{doc.version}) • {doc.is_confidential ? 'Confidential' : 'Public'}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Extraction Template</label>
                <select
                  value={extractionTemplate}
                  onChange={(e) => setExtractionTemplate(e.target.value)}
                  className="w-full text-xs border border-slate-300 rounded-lg p-2.5 bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="policy">Policy & Compliance Template</option>
                  <option value="runbook">Engineering Runbook Template</option>
                  <option value="sla">SLA & Incident Response Template</option>
                  <option value="general">General Enterprise Template</option>
                </select>
              </div>
            </div>

            <div className="mt-5 flex items-center justify-between">
              <button
                onClick={handleRunExtraction}
                disabled={isExtracting || !extractionDocId}
                className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-all shadow-xs cursor-pointer"
              >
                {isExtracting ? (
                  <>
                    <RefreshCw size={14} className="animate-spin" />
                    <span>Extracting Structured Fields...</span>
                  </>
                ) : (
                  <>
                    <FileCheck size={14} />
                    <span>Extract Fields & Risks</span>
                  </>
                )}
              </button>

              <span className="text-[11px] text-slate-400">
                Tool Allowlist: <code className="bg-slate-100 px-1 py-0.5 rounded text-slate-600">extract_structured_fields</code>
              </span>
            </div>

            {extractionError && (
              <div className="mt-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-xs flex items-center gap-2">
                <AlertTriangle size={16} className="shrink-0 text-red-500" />
                <span>{extractionError}</span>
              </div>
            )}
          </div>

          {/* Structured Extraction Result */}
          {extractionResult && (
            <div className="space-y-6">
              <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center gap-3 text-xs text-slate-700">
                  <span className="font-semibold text-slate-900">{extractionResult.title} (v{extractionResult.version})</span>
                  <span className="text-slate-400">•</span>
                  <span>{extractionResult.requirements.length} Requirements</span>
                  <span className="text-slate-400">•</span>
                  <span>{extractionResult.risks.length} Risks Identified</span>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleExport('structured_extraction', extractionResult, 'markdown', `${extractionResult.title}_Extraction`)}
                    disabled={isExporting}
                    className="flex items-center gap-1.5 px-3 py-1.5 border border-slate-300 rounded-lg text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
                  >
                    <Download size={13} />
                    <span>Export MD</span>
                  </button>

                  <button
                    onClick={() => handleExport('structured_extraction', extractionResult, 'pdf', `${extractionResult.title}_Extraction`)}
                    disabled={isExporting}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-medium transition-colors cursor-pointer"
                  >
                    <Download size={13} />
                    <span>Export PDF</span>
                  </button>
                </div>
              </div>

              {/* Custodian & Governance Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Custodian / Owner</span>
                  <div className="text-sm font-semibold text-slate-900">
                    {extractionResult.owner?.value || 'Department Custodian'}
                  </div>
                  <div className="text-[10px] text-indigo-600 font-mono mt-1">
                    {extractionResult.owner?.citation || 'Metadata'}
                  </div>
                </div>

                <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Effective Date</span>
                  <div className="text-sm font-semibold text-slate-900">
                    {extractionResult.effective_date?.value || 'Active Policy'}
                  </div>
                  <div className="text-[10px] text-indigo-600 font-mono mt-1">
                    {extractionResult.effective_date?.citation || 'Metadata'}
                  </div>
                </div>

                <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Review Cycle / SLA</span>
                  <div className="text-sm font-semibold text-slate-900 truncate">
                    {extractionResult.deadline_or_cycle?.value || 'Periodic Audit'}
                  </div>
                  <div className="text-[10px] text-indigo-600 font-mono mt-1">
                    {extractionResult.deadline_or_cycle?.citation || 'Metadata'}
                  </div>
                </div>
              </div>

              {/* Requirements & Risks Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Requirements */}
                <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
                  <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                    <CheckCircle2 size={15} className="text-emerald-500" />
                    <span>Operational Requirements</span>
                  </h3>
                  <div className="space-y-2.5">
                    {extractionResult.requirements.map((req, idx) => (
                      <div key={idx} className="p-3 bg-slate-50 border border-slate-100 rounded-lg text-xs">
                        <p className="text-slate-800">{req.value}</p>
                        <div className="mt-1 text-[10px] text-indigo-600 font-mono">{req.citation}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Risk Matrix */}
                <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
                  <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                    <AlertTriangle size={15} className="text-amber-500" />
                    <span>Risk Matrix & Severity</span>
                  </h3>
                  <div className="space-y-2.5">
                    {extractionResult.risks.length > 0 ? (
                      extractionResult.risks.map((risk, idx) => (
                        <div key={idx} className="p-3 border rounded-lg text-xs border-amber-200 bg-amber-50/40">
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-semibold text-slate-900">{risk.risk_title}</span>
                            <span className="uppercase text-[9px] font-bold px-1.5 py-0.5 rounded bg-amber-200 text-amber-900">
                              {risk.severity}
                            </span>
                          </div>
                          <p className="text-slate-600 text-[11px] mt-1">{risk.description}</p>
                          <div className="mt-2 text-[10px] text-indigo-600 font-mono">{risk.citation}</div>
                        </div>
                      ))
                    ) : (
                      <div className="text-xs text-slate-400 italic p-4 text-center">
                        No critical vulnerabilities or high risks flagged in this document version.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ============================================================== */}
      {/* 4. EXECUTION HISTORY TAB                                       */}
      {/* ============================================================== */}
      {activeWorkflowTab === 'history' && (
        <div className="mt-6 bg-white border border-slate-200 rounded-xl p-6 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Workflow Execution Telemetry</h2>
              <p className="text-xs text-slate-500">
                Audited history of multi-step knowledge workflows completed under your session credentials.
              </p>
            </div>
            <button
              onClick={loadHistory}
              disabled={isLoadingHistory}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 cursor-pointer"
            >
              <RefreshCw size={13} className={isLoadingHistory ? 'animate-spin' : ''} />
              <span>Refresh</span>
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-200 text-slate-400 uppercase text-[10px] tracking-wider">
                  <th className="py-2.5 px-3 font-semibold">Workflow ID</th>
                  <th className="py-2.5 px-3 font-semibold">Type</th>
                  <th className="py-2.5 px-3 font-semibold">Title</th>
                  <th className="py-2.5 px-3 font-semibold">Status</th>
                  <th className="py-2.5 px-3 font-semibold">Duration</th>
                  <th className="py-2.5 px-3 font-semibold">Executed At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {workflowHistory.length > 0 ? (
                  workflowHistory.map((item) => (
                    <tr key={item.id} className="hover:bg-slate-50">
                      <td className="py-2.5 px-3 font-mono text-slate-500 text-[11px]">{item.id.slice(0, 8)}...</td>
                      <td className="py-2.5 px-3 font-medium text-slate-800">
                        <span className="bg-slate-100 px-2 py-0.5 rounded text-[11px]">{item.workflow_type}</span>
                      </td>
                      <td className="py-2.5 px-3 text-slate-700">{item.title}</td>
                      <td className="py-2.5 px-3">
                        <span className="text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded font-semibold text-[10px] uppercase">
                          {item.status}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-mono text-slate-500">{item.total_duration_ms} ms</td>
                      <td className="py-2.5 px-3 text-slate-400 text-[11px]">
                        {new Date(item.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-400 italic">
                      No workflows executed yet. Launch a version comparison, collection summary, or extraction above.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
