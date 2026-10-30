import React, { useState } from 'react';
import { X, UserPlus, AlertCircle, CheckCircle2 } from 'lucide-react';
import { api } from '../api/client';
import { DocumentItem } from '../types';

interface GrantModalProps {
  document: DocumentItem | null;
  onClose: () => void;
  onSuccess: () => void;
}

export const GrantModal: React.FC<GrantModalProps> = ({
  document,
  onClose,
  onSuccess,
}) => {
  const [granteeUserId, setGranteeUserId] = useState('');
  const [permission, setPermission] = useState('read');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  if (!document) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!granteeUserId.trim()) {
      setError('Please provide a valid User ID to grant access.');
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setSuccess(false);

    try {
      await api.documents.createGrant(document.id, {
        grantee_user_id: granteeUserId.trim(),
        permission,
      });
      setSuccess(true);
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 900);
    } catch (err: any) {
      setError(err?.message || 'Failed to create document grant');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-md w-full border border-slate-200 overflow-hidden animate-scaleIn">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-indigo-50 text-indigo-600">
              <UserPlus size={18} />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-800">Assign Explicit Document Grant</h3>
              <p className="text-xs text-slate-500 truncate max-w-[280px]">For: {document.title}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 transition-colors cursor-pointer"
          >
            <X size={16} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-center gap-2">
              <AlertCircle size={15} className="shrink-0 text-red-500" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-700 flex items-center gap-2">
              <CheckCircle2 size={15} className="shrink-0 text-emerald-500" />
              <span>Grant successfully applied!</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Grantee User ID (UUID)
            </label>
            <input
              type="text"
              required
              value={granteeUserId}
              onChange={(e) => setGranteeUserId(e.target.value)}
              placeholder="e.g. 11111111-1111-1111-1111-111111111111"
              className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 font-mono"
              disabled={isSubmitting}
            />
            <p className="text-[11px] text-slate-400 mt-1">
              Overrides department isolation for this specific user.
            </p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Permission Level
            </label>
            <select
              value={permission}
              onChange={(e) => setPermission(e.target.value)}
              className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 bg-white"
              disabled={isSubmitting}
            >
              <option value="read">Read (Retrieve & Query Grounding)</option>
              <option value="manage">Manage (Read + Edit Grants)</option>
            </select>
          </div>

          {/* Actions */}
          <div className="pt-2 flex items-center justify-end gap-2 border-t border-slate-200">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-3.5 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
            >
              {isSubmitting ? 'Granting...' : 'Confirm Grant'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

