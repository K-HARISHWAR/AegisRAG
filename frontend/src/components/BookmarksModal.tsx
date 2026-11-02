import React from 'react';
import { Bookmark, Trash2, X, ShieldCheck, FileText } from 'lucide-react';
import { ThreadBookmark } from '../types';

interface BookmarksModalProps {
  isOpen: boolean;
  onClose: () => void;
  bookmarks: ThreadBookmark[];
  onDeleteBookmark: (bookmarkId: string) => Promise<void>;
}

export const BookmarksModal: React.FC<BookmarksModalProps> = ({
  isOpen,
  onClose,
  bookmarks,
  onDeleteBookmark,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-2xl w-full p-6 shadow-2xl relative max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 bg-amber-500/10 rounded-lg text-amber-400">
              <Bookmark className="w-5 h-5 fill-amber-400/20" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white">Saved Snippets & Bookmarks</h2>
              <p className="text-xs text-slate-400">
                Server-verified bookmarks with real-time permission revalidation
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 p-1 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Security badge notice */}
        <div className="mt-3 p-2.5 bg-indigo-950/40 border border-indigo-800/40 rounded-lg flex items-center space-x-2 text-xs text-indigo-300">
          <ShieldCheck className="w-4 h-4 shrink-0 text-indigo-400" />
          <span>
            Snippets are strictly filtered by current PostgreSQL access rights. If access to a document is revoked, its bookmarks are automatically removed from view.
          </span>
        </div>

        {/* List of bookmarks */}
        <div className="flex-1 overflow-y-auto mt-4 space-y-3 pr-1">
          {bookmarks.length === 0 ? (
            <div className="text-center py-12 text-slate-500 text-sm">
              <Bookmark className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p>No saved snippets yet.</p>
              <p className="text-xs text-slate-600 mt-1">
                Click "Save Snippet" on any citation badge in chat responses to bookmark it.
              </p>
            </div>
          ) : (
            bookmarks.map((bm) => (
              <div
                key={bm.id}
                className="bg-slate-950/60 border border-slate-800 rounded-lg p-3.5 hover:border-slate-700 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-2">
                    <FileText className="w-4 h-4 text-indigo-400" />
                    <span className="text-sm font-semibold text-white">{bm.title}</span>
                    <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
                      {bm.location}
                    </span>
                  </div>
                  <button
                    onClick={() => onDeleteBookmark(bm.id)}
                    className="text-slate-500 hover:text-red-400 p-1 rounded hover:bg-slate-800 transition-colors"
                    title="Remove Bookmark"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                <div className="mt-2.5 p-2.5 bg-slate-900/90 rounded text-xs text-slate-300 font-mono leading-relaxed border border-slate-800/80">
                  {bm.snippet}
                </div>

                {bm.notes && (
                  <div className="mt-2 text-xs text-amber-300/80 italic">
                    Note: "{bm.notes}"
                  </div>
                )}

                <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500">
                  <span className="font-mono">Hash: {bm.content_hash.slice(0, 12)}...</span>
                  <span>{new Date(bm.created_at).toLocaleDateString()}</span>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="pt-4 border-t border-slate-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
