import React, { useEffect, useState } from 'react';
import {
  Files,
  UploadCloud,
  Search,
  FileText,
  Lock,
  RefreshCw,
  Trash2,
  Eye,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { DocumentItem } from '../types';
import { DocumentUploadModal } from '../components/DocumentUploadModal';
import { DocumentViewerModal } from '../components/DocumentViewerModal';
import { GrantModal } from '../components/GrantModal';

export const DocumentsPage: React.FC = () => {
  const { user, isManager, isAdmin } = useAuth();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Modals state
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [selectedDocForView, setSelectedDocForView] = useState<DocumentItem | null>(null);
  const [selectedDocForGrant, setSelectedDocForGrant] = useState<DocumentItem | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const fetchDocuments = async () => {
    setLoading(true);
    setError(null);
    try {
      const docs = await api.documents.list();
      setDocuments(docs);
    } catch (err: any) {
      setError(err?.message || 'Failed to retrieve authorized documents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const handleReindex = async (doc: DocumentItem) => {
    try {
      const res = await api.documents.reindex(doc.id);
      setActionMessage(`Document "${doc.title}" re-indexed: ${res.indexed_chunks} chunks.`);
      setTimeout(() => setActionMessage(null), 4000);
      fetchDocuments();
    } catch (err: any) {
      setError(err?.message || 'Failed to re-index document');
    }
  };

  const handleDelete = async (doc: DocumentItem) => {
    if (!window.confirm(`Are you sure you want to delete "${doc.title}"?`)) return;

    try {
      await api.documents.delete(doc.id);
      setActionMessage(`Document "${doc.title}" has been removed.`);
      setTimeout(() => setActionMessage(null), 4000);
      fetchDocuments();
    } catch (err: any) {
      setError(err?.message || 'Failed to delete document');
    }
  };

  // Departments list for filter / upload modal
  const standardDepartments = [
    { id: user?.department_id || 'engineering-dept', name: 'Engineering' },
    { id: 'hr-dept-id', name: 'HR' },
  ];

  const filteredDocs = documents.filter((doc) => {
    const matchesSearch = doc.title.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSearch;
  });

  const canUpload = isManager || isAdmin;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Page Title & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Files className="text-indigo-600" size={24} />
            Enterprise Document Repository
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Access-controlled knowledge store. All queries and chunk citations are filtered by
            PostgreSQL permissions.
          </p>
        </div>

        {canUpload && (
          <button
            onClick={() => setIsUploadOpen(true)}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs flex items-center gap-2 cursor-pointer transition-colors"
          >
            <UploadCloud size={16} />
            <span>Upload Document</span>
          </button>
        )}
      </div>

      {/* Action Notification */}
      {actionMessage && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 flex items-center gap-2">
          <CheckCircle2 size={16} className="text-emerald-500 shrink-0" />
          <span>{actionMessage}</span>
        </div>
      )}

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-800 flex items-center gap-2">
          <AlertCircle size={16} className="text-red-500 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Search & Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-80">
          <Search size={16} className="absolute left-3 top-2.5 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search document titles..."
            className="w-full pl-9 pr-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
          />
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="font-medium">Total Visible:</span>
          <span className="px-2 py-0.5 bg-slate-100 rounded font-semibold text-slate-700">
            {filteredDocs.length} Documents
          </span>
          <button
            onClick={fetchDocuments}
            disabled={loading}
            className="p-2 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 cursor-pointer transition-colors"
            title="Refresh document list"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Documents Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-slate-400 text-xs">
            <span className="inline-block w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mb-2" />
            <p>Loading authorized documents...</p>
          </div>
        ) : filteredDocs.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-xs">
            <Files size={32} className="mx-auto mb-2 text-slate-300" />
            <p className="font-semibold text-slate-600">No documents found</p>
            <p className="text-slate-400 mt-0.5">
              No matching documents are permitted for your account in this department.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
                  <th className="py-3 px-4">Title</th>
                  <th className="py-3 px-3">Type</th>
                  <th className="py-3 px-3">Size</th>
                  <th className="py-3 px-3">Confidentiality</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-3">Grants</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {filteredDocs.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="py-3.5 px-4">
                      <div className="font-medium text-slate-900 flex items-center gap-2">
                        <FileText size={16} className="text-slate-400 shrink-0" />
                        <span className="truncate max-w-xs" title={doc.title}>
                          {doc.title}
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-400 font-mono">
                        ID: {doc.id.slice(0, 8)}...
                      </span>
                    </td>
                    <td className="py-3.5 px-3 uppercase font-mono text-[11px] text-slate-500">
                      {doc.file_type}
                    </td>
                    <td className="py-3.5 px-3 text-slate-500">
                      {(doc.file_size_bytes / 1024).toFixed(1)} KB
                    </td>
                    <td className="py-3.5 px-3">
                      {doc.is_confidential ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                          <Lock size={10} /> Confidential
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600">
                          Standard
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold ${
                          doc.status === 'indexed'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : doc.status === 'uploaded'
                            ? 'bg-blue-50 text-blue-700 border border-blue-200'
                            : 'bg-slate-100 text-slate-700'
                        }`}
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-current" />
                        {doc.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-3">
                      <span className="px-2 py-0.5 bg-slate-100 rounded text-[10px] font-medium text-slate-600">
                        {doc.grants ? doc.grants.length : 0} grants
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => setSelectedDocForView(doc)}
                          className="p-1.5 text-slate-600 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors cursor-pointer"
                          title="View extracted passages and citation coordinates"
                        >
                          <Eye size={15} />
                        </button>

                        {(isManager || isAdmin) && (
                          <>
                            <button
                              onClick={() => handleReindex(doc)}
                              className="p-1.5 text-slate-600 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors cursor-pointer"
                              title="Re-index document into vector store"
                            >
                              <RefreshCw size={15} />
                            </button>
                            <button
                              onClick={() => handleDelete(doc)}
                              className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors cursor-pointer"
                              title="Delete document"
                            >
                              <Trash2 size={15} />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modals */}
      <DocumentUploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={fetchDocuments}
        departments={standardDepartments}
      />

      <DocumentViewerModal
        document={selectedDocForView}
        onClose={() => setSelectedDocForView(null)}
        onOpenGrantModal={(doc) => {
          setSelectedDocForView(null);
          setSelectedDocForGrant(doc);
        }}
      />

      <GrantModal
        document={selectedDocForGrant}
        onClose={() => setSelectedDocForGrant(null)}
        onSuccess={fetchDocuments}
      />
    </div>
  );
};
