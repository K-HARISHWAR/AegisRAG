import React, { useEffect, useState } from 'react';
import { X, UploadCloud, AlertCircle, CheckCircle2, Lock, GitBranch } from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { DocumentItem } from '../types';

interface DocumentUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  departments: { id: string; name: string }[];
  revisingDocument?: DocumentItem | null;
}

export const DocumentUploadModal: React.FC<DocumentUploadModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  departments,
  revisingDocument = null,
}) => {
  const { user, isAdmin } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState(revisingDocument ? revisingDocument.title : '');
  const [departmentId, setDepartmentId] = useState<string>(
    revisingDocument
      ? revisingDocument.department_id
      : user?.department_id || (departments[0]?.id ?? '')
  );
  const [isConfidential, setIsConfidential] = useState(
    revisingDocument ? revisingDocument.is_confidential : false
  );
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    if (revisingDocument) {
      setTitle(revisingDocument.title);
      setDepartmentId(revisingDocument.department_id);
      setIsConfidential(revisingDocument.is_confidential);
    } else {
      setTitle('');
      setDepartmentId(user?.department_id || (departments[0]?.id ?? ''));
      setIsConfidential(false);
    }
    setFile(null);
    setError(null);
    setSuccessMessage(null);
  }, [revisingDocument, isOpen]);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      if (!title) {
        // Strip extension for friendly default title
        const baseName = selectedFile.name.replace(/\.[^/.]+$/, '');
        setTitle(baseName);
      }
      setError(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a file to upload.');
      return;
    }

    if (file.size > 20 * 1024 * 1024) {
      setError('File size exceeds the 20 MB limit.');
      return;
    }

    const deptId = isAdmin ? departmentId : (user?.department_id || departmentId);
    if (!deptId) {
      setError('A valid department assignment is required to upload.');
      return;
    }

    setIsUploading(true);
    setError(null);
    setSuccessMessage(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('department_id', deptId);
    formData.append('title', title || file.name);
    formData.append('is_confidential', isConfidential ? 'true' : 'false');
    if (revisingDocument) {
      formData.append('revises_document_id', revisingDocument.id);
    }

    try {
      const res = await api.documents.upload(formData);
      setSuccessMessage(
        revisingDocument
          ? `Revision v${res.document.version} uploaded successfully. Previous revision superseded.`
          : `Document successfully ingested and indexed (${res.document.title})`
      );
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1000);
    } catch (err: any) {
      setError(err?.message || 'Failed to upload document');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-md w-full border border-slate-200 overflow-hidden animate-scaleIn">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-indigo-50 text-indigo-600">
              {revisingDocument ? <GitBranch size={20} /> : <UploadCloud size={20} />}
            </div>
            <div>
              <h3 className="text-base font-semibold text-slate-800">
                {revisingDocument
                  ? `Upload Revision (supersedes v${revisingDocument.version})`
                  : 'Upload Enterprise Document'}
              </h3>
              <p className="text-xs text-slate-500">
                {revisingDocument
                  ? 'Creates an updated revision while preserving audit history'
                  : 'Auto-parsed and indexed with RBAC safeguards'}
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

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-center gap-2">
              <AlertCircle size={16} className="shrink-0 text-red-500" />
              <span>{error}</span>
            </div>
          )}

          {successMessage && (
            <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-700 flex items-center gap-2">
              <CheckCircle2 size={16} className="shrink-0 text-emerald-500" />
              <span>{successMessage}</span>
            </div>
          )}

          {/* File Picker */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Select Document (.pdf, .docx, .xlsx - max 20MB)
            </label>
            <div className="border-2 border-dashed border-slate-300 rounded-lg p-5 text-center hover:border-indigo-400 transition-colors bg-slate-50/50">
              <input
                type="file"
                id="doc-file-input"
                accept=".pdf,.docx,.xlsx"
                onChange={handleFileChange}
                className="hidden"
                disabled={isUploading}
              />
              <label
                htmlFor="doc-file-input"
                className="cursor-pointer flex flex-col items-center justify-center gap-1.5"
              >
                <UploadCloud size={28} className="text-slate-400" />
                <span className="text-xs font-medium text-indigo-600 hover:underline">
                  {file ? file.name : 'Choose a file or drag & drop here'}
                </span>
                <span className="text-[11px] text-slate-400">
                  {file ? `${(file.size / (1024 * 1024)).toFixed(2)} MB` : 'PDF, DOCX, or XLSX only'}
                </span>
              </label>
            </div>
          </div>

          {/* Title */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Document Display Title
            </label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Q1 Infrastructure Runbook"
              className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              disabled={isUploading}
            />
          </div>

          {/* Department */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Department Classification
            </label>
            {isAdmin ? (
              <select
                value={departmentId}
                onChange={(e) => setDepartmentId(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 bg-white"
                disabled={isUploading}
              >
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            ) : (
              <div className="px-3 py-2 text-xs border border-slate-200 bg-slate-100 rounded-lg text-slate-600 flex items-center justify-between">
                <span>{user?.department?.name || 'Assigned Department'}</span>
                <span className="text-[11px] text-slate-400">Locked to your department</span>
              </div>
            )}
          </div>

          {/* Confidentiality Toggle */}
          <div className="p-3 rounded-lg border border-slate-200 bg-slate-50/70 flex items-start gap-3">
            <input
              type="checkbox"
              id="is_confidential"
              checked={isConfidential}
              onChange={(e) => setIsConfidential(e.target.checked)}
              className="mt-0.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
              disabled={isUploading}
            />
            <label htmlFor="is_confidential" className="text-xs cursor-pointer select-none">
              <span className="font-semibold text-slate-800 flex items-center gap-1">
                <Lock size={12} className="text-amber-600" />
                Department Confidential
              </span>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Restricts retrieval to department managers only. Regular employees in the same
                department cannot access this document without explicit grants.
              </p>
            </label>
          </div>

          {/* Actions */}
          <div className="pt-2 flex items-center justify-end gap-2 border-t border-slate-200">
            <button
              type="button"
              onClick={onClose}
              disabled={isUploading}
              className="px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isUploading}
              className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
            >
              {isUploading ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Indexing...</span>
                </>
              ) : (
                <>
                  <UploadCloud size={14} />
                  <span>Upload & Index</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
