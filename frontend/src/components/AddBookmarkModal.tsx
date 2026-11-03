import React, { useState } from 'react';
import { Bookmark, X, FileText, Check } from 'lucide-react';
import { Citation, ThreadBookmarkCreateRequest } from '../types';

interface AddBookmarkModalProps {
  isOpen: boolean;
  onClose: () => void;
  citation: Citation | null;
  onSaveBookmark: (payload: ThreadBookmarkCreateRequest) => Promise<void>;
}

export const AddBookmarkModal: React.FC<AddBookmarkModalProps> = ({
  isOpen,
  onClose,
  citation,
  onSaveBookmark,
}) => {
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen || !citation) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      await onSaveBookmark({
        document_id: citation.document_id,
        title: citation.document_title,
        location: citation.location,
        snippet: citation.snippet,
        content_hash: citation.content_hash,
        notes: notes.trim() || undefined,
      });
      setNotes('');
      onClose();
    } catch (err: any) {
      setError(err?.message || 'Failed to save bookmark. Ensure active permissions.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-lg w-full p-6 shadow-2xl relative">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center space-x-2">
            <Bookmark className="w-5 h-5 text-amber-400 fill-amber-400/20" />
            <h2 className="text-base font-semibold text-white">Save Citation Snippet</h2>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 p-1 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          {error && (
            <div className="p-2.5 bg-red-950/50 border border-red-800 text-red-300 rounded text-xs">
              {error}
            </div>
          )}

          <div>
            <label className="text-xs font-semibold text-slate-400 block mb-1">Document & Location</label>
            <div className="flex items-center space-x-2 bg-slate-950 p-2.5 rounded border border-slate-800 text-xs text-white">
              <FileText className="w-4 h-4 text-indigo-400 shrink-0" />
              <span className="font-medium truncate">{citation.document_title}</span>
              <span className="bg-slate-800 px-1.5 py-0.5 rounded text-[11px] font-mono text-slate-300 shrink-0">
                {citation.location}
              </span>
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-400 block mb-1">Snippet Preview</label>
            <div className="bg-slate-950 p-2.5 rounded border border-slate-800 text-xs text-slate-300 font-mono max-h-28 overflow-y-auto leading-relaxed">
              {citation.snippet}
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-400 block mb-1">Personal Note (Optional)</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g., Reference for Q4 infrastructure upgrade"
              rows={3}
              maxLength={1000}
              className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div className="flex justify-end space-x-2 pt-2 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center space-x-1.5 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded text-xs font-medium transition-colors"
            >
              <Check className="w-3.5 h-3.5" />
              <span>{isSubmitting ? 'Saving...' : 'Save Bookmark'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

