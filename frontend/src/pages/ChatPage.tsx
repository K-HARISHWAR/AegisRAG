import React, { useState } from 'react';
import {
  Send,
  Sparkles,
  AlertTriangle,
  FileText,
  Clock,
  Layers,
  Shield,
  RefreshCw,
  ExternalLink,
  CheckCircle2,
} from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { ChatMessage, Citation, EvidenceDiagnostics, RetrievedChunk } from '../types';
import { CitationDrawer } from '../components/CitationDrawer';

export const ChatPage: React.FC = () => {
  const { user, departmentName, primaryRole } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputQuery, setInputQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Citation Drawer state
  const [selectedCitations, setSelectedCitations] = useState<Citation[]>([]);
  const [selectedChunks, setSelectedChunks] = useState<RetrievedChunk[]>([]);
  const [selectedQuery, setSelectedQuery] = useState<string>('');
  const [selectedEvidenceDiagnostics, setSelectedEvidenceDiagnostics] = useState<EvidenceDiagnostics | null | undefined>(null);
  const [selectedEvidenceLevel, setSelectedEvidenceLevel] = useState<string | undefined>(undefined);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  // Persona-tailored starter prompts
  const starterPrompts = [
    {
      title: 'Deployment Procedure',
      query: 'What is the primary deployment procedure for production services?',
      dept: 'Engineering',
    },
    {
      title: 'API Key Rotation',
      query: 'How do engineers rotate service account API keys?',
      dept: 'Engineering',
    },
    {
      title: 'Disciplinary Protocol',
      query: 'What are the performance improvement plan (PIP) escalation timelines?',
      dept: 'HR',
    },
    {
      title: 'Leave Policy',
      query: 'What is the annual paid time off (PTO) policy for full-time employees?',
      dept: 'HR',
    },
    {
      title: 'Executive Compensation',
      query: 'What is the executive bonus distribution formula and compensation scale?',
      dept: 'HR (Confidential)',
    },
  ];

  const handleSend = async (queryText?: string) => {
    const q = (queryText || inputQuery).trim();
    if (!q || isLoading) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: q,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputQuery('');
    setIsLoading(true);

    try {
      const response = await api.chat.query({ query: q });

      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        sender: 'assistant',
        text: response.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: response.citations,
        retrievedChunks: response.retrieved_chunks,
        abstained: response.abstained,
        evidenceLevel: response.evidence_level,
        abstentionReason: response.abstention_reason,
        evidenceDiagnostics: response.evidence_diagnostics,
        executionTimeMs: response.execution_time_ms,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      const errorMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        sender: 'assistant',
        text: err?.message || 'An error occurred while processing your request.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        error: true,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleOpenDrawer = (message: ChatMessage) => {
    setSelectedCitations(message.citations || []);
    setSelectedChunks(message.retrievedChunks || []);
    setSelectedQuery(message.text);
    setSelectedEvidenceDiagnostics(message.evidenceDiagnostics);
    setSelectedEvidenceLevel(message.evidenceLevel);
    setIsDrawerOpen(true);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] max-w-5xl mx-auto px-4 py-6">
      {/* Scope Banner */}
      <div className="mb-4 p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between text-xs text-slate-600">
        <div className="flex items-center gap-2">
          <Shield size={16} className="text-indigo-600" />
          <span>
            Active RBAC Session:{' '}
            <strong className="text-slate-800">{user?.email}</strong> (
            <span className="text-indigo-600 font-semibold">{departmentName}</span> •{' '}
            <span className="font-semibold">{primaryRole}</span>)
          </span>
        </div>
        <span className="text-[11px] text-slate-400">Two-Stage PostgreSQL RBAC Active</span>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6">
            <div className="w-12 h-12 rounded-2xl bg-indigo-100 text-indigo-600 flex items-center justify-center mb-4">
              <Sparkles size={24} />
            </div>
            <h2 className="text-lg font-bold text-slate-800 mb-1">
              How can AegisRAG assist you today?
            </h2>
            <p className="text-xs text-slate-500 max-w-md mb-6 leading-relaxed">
              Ask questions grounded directly in your department's enterprise documents. Access to
              confidential or cross-department files is strictly governed by server RBAC.
            </p>

            {/* Quick Starters */}
            <div className="w-full max-w-xl grid grid-cols-1 sm:grid-cols-2 gap-2 text-left">
              {starterPrompts.map((s, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSend(s.query)}
                  className="p-3 bg-white border border-slate-200 hover:border-indigo-400 rounded-xl shadow-xs transition-all text-xs cursor-pointer group"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-slate-800 group-hover:text-indigo-600">
                      {s.title}
                    </span>
                    <span className="text-[10px] text-slate-400 px-1.5 py-0.5 bg-slate-100 rounded">
                      {s.dept}
                    </span>
                  </div>
                  <p className="text-slate-500 line-clamp-2 text-[11px]">{s.query}</p>
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${
                msg.sender === 'user' ? 'items-end' : 'items-start'
              }`}
            >
              <div
                className={`max-w-2xl rounded-2xl p-4 text-xs leading-relaxed shadow-xs ${
                  msg.sender === 'user'
                    ? 'bg-indigo-600 text-white rounded-tr-xs'
                    : msg.error
                    ? 'bg-red-50 border border-red-200 text-red-800 rounded-tl-xs'
                    : msg.abstained
                    ? 'bg-amber-50/70 border border-amber-200 text-amber-900 rounded-tl-xs'
                    : 'bg-white border border-slate-200 text-slate-800 rounded-tl-xs'
                }`}
              >
                {/* Evidence Level Badge */}
                {msg.sender === 'assistant' && !msg.error && msg.evidenceLevel && (
                  <div className="mb-2">
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                        msg.evidenceLevel === 'strong'
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : msg.evidenceLevel === 'limited'
                          ? 'bg-amber-50 text-amber-700 border-amber-200'
                          : 'bg-rose-50 text-rose-700 border-rose-200'
                      }`}
                    >
                      {msg.evidenceLevel === 'strong' ? (
                        <CheckCircle2 size={10} />
                      ) : (
                        <AlertTriangle size={10} />
                      )}
                      {msg.evidenceLevel === 'strong'
                        ? 'Strong Evidence'
                        : msg.evidenceLevel === 'limited'
                        ? 'Limited Evidence'
                        : 'Insufficient Evidence'}
                    </span>
                  </div>
                )}

                {/* Abstention Banner if applicable */}
                {msg.abstained && (
                  <div className="flex items-center gap-1.5 text-amber-700 font-semibold mb-2 pb-2 border-b border-amber-200/60">
                    <AlertTriangle size={14} />
                    <span>{msg.abstentionReason || 'Insufficient Evidence / Access Restricted'}</span>
                  </div>
                )}

                <p className="whitespace-pre-wrap">{msg.text}</p>

                {/* Inline Citations & Diagnostics Bar */}
                {msg.sender === 'assistant' && !msg.error && (
                  <div className="mt-3 pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2 text-[11px]">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {msg.citations && msg.citations.length > 0 ? (
                        <>
                          <span className="text-slate-400 font-medium">Sources:</span>
                          {msg.citations.map((c, i) => (
                            <button
                              key={i}
                              onClick={() => handleOpenDrawer(msg)}
                              className="px-2 py-0.5 rounded bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-medium flex items-center gap-1 cursor-pointer transition-colors border border-indigo-100"
                              title={`View passage quote: ${c.document_title} (${c.location})`}
                            >
                              <FileText size={11} />
                              <span>{c.document_title}</span>
                              <span className="text-indigo-400 font-semibold">({c.location})</span>
                            </button>
                          ))}
                        </>
                      ) : (
                        <span className="text-slate-400 italic">No source documents cited</span>
                      )}
                    </div>

                    <div className="flex items-center gap-3 text-slate-400 ml-auto">
                      {msg.executionTimeMs && (
                        <span className="flex items-center gap-1" title="Generation latency">
                          <Clock size={11} />
                          {msg.executionTimeMs.toFixed(0)}ms
                        </span>
                      )}
                      {msg.retrievedChunks && (
                        <span
                          className="flex items-center gap-1"
                          title="Retrieved candidate chunks"
                        >
                          <Layers size={11} />
                          {msg.retrievedChunks.length} passages
                        </span>
                      )}
                      {((msg.citations && msg.citations.length > 0) || msg.evidenceDiagnostics) && (
                        <button
                          onClick={() => handleOpenDrawer(msg)}
                          className="text-indigo-600 hover:underline flex items-center gap-0.5 cursor-pointer font-medium"
                        >
                          Details <ExternalLink size={10} />
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
              <span className="text-[10px] text-slate-400 mt-1 px-1">{msg.timestamp}</span>
            </div>
          ))
        )}

        {isLoading && (
          <div className="flex items-center gap-2 text-xs text-slate-400 p-2">
            <span className="w-4 h-4 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            <span>Retrieving authorized passages and generating grounded response...</span>
          </div>
        )}
      </div>

      {/* Query Input Form */}
      <div className="mt-4 pt-2">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="relative flex items-center bg-white border border-slate-300 rounded-xl shadow-xs focus-within:ring-2 focus-within:ring-indigo-500/20 focus-within:border-indigo-500 transition-all"
        >
          <input
            type="text"
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            placeholder="Ask a question about internal procedures, runbooks, or policies..."
            className="w-full px-4 py-3 text-xs bg-transparent focus:outline-hidden text-slate-800 placeholder-slate-400"
            disabled={isLoading}
          />
          <div className="pr-2 flex items-center gap-1">
            {messages.length > 0 && (
              <button
                type="button"
                onClick={() => setMessages([])}
                className="p-2 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
                title="Reset conversation"
              >
                <RefreshCw size={14} />
              </button>
            )}
            <button
              type="submit"
              disabled={isLoading || !inputQuery.trim()}
              className="p-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors cursor-pointer disabled:opacity-40"
              title="Submit Query"
            >
              <Send size={14} />
            </button>
          </div>
        </form>
        <p className="text-[11px] text-center text-slate-400 mt-2">
          Grounded Generation: All responses are verified against PostgreSQL RBAC and citation
          coordinates.
        </p>
      </div>

      {/* Slide-out Citation Drawer */}
      <CitationDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        citations={selectedCitations}
        retrievedChunks={selectedChunks}
        queryText={selectedQuery}
        evidenceDiagnostics={selectedEvidenceDiagnostics}
        evidenceLevel={selectedEvidenceLevel}
      />
    </div>
  );
};
