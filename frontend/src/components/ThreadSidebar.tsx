import React, { useState } from 'react';
import {
  Plus,
  MessageSquare,
  Archive,
  Trash2,
  Edit2,
  Bookmark,
  Check,
  X,
  RotateCcw,
  Clock,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { ThreadBookmark, ThreadSummary } from '../types';

interface ThreadSidebarProps {
  threads: ThreadSummary[];
  activeThreadId: string | null;
  onSelectThread: (threadId: string) => void;
  onNewThread: () => void;
  onRenameThread: (threadId: string, newTitle: string) => Promise<void>;
  onArchiveToggle: (threadId: string, currentArchived: boolean) => Promise<void>;
  onDeleteThread: (threadId: string) => Promise<void>;
  bookmarks: ThreadBookmark[];
  onOpenBookmarks: () => void;
  isLoading?: boolean;
}

export const ThreadSidebar: React.FC<ThreadSidebarProps> = ({
  threads,
  activeThreadId,
  onSelectThread,
  onNewThread,
  onRenameThread,
  onArchiveToggle,
  onDeleteThread,
  bookmarks,
  onOpenBookmarks,
  isLoading = false,
}) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [editingThreadId, setEditingThreadId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const filteredThreads = threads.filter((t) => (showArchived ? t.is_archived : !t.is_archived));

  const handleStartRename = (thread: ThreadSummary, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingThreadId(thread.id);
    setEditTitle(thread.title);
  };

  const handleSaveRename = async (threadId: string, e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (editTitle.trim()) {
      await onRenameThread(threadId, editTitle.trim());
    }
    setEditingThreadId(null);
  };

  const handleCancelRename = () => {
    setEditingThreadId(null);
    setEditTitle('');
  };

  const formatDate = (isoString: string) => {
    const d = new Date(isoString);
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  if (isCollapsed) {
    return (
      <div className="w-14 bg-slate-900 border-r border-slate-800 flex flex-col items-center py-4 space-y-4 shrink-0 transition-all duration-200">
        <button
          onClick={() => setIsCollapsed(false)}
          className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
          title="Expand Workspaces"
        >
          <ChevronRight className="w-5 h-5" />
        </button>
        <button
          onClick={onNewThread}
          className="p-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-colors"
          title="New Conversation"
        >
          <Plus className="w-5 h-5" />
        </button>
        <button
          onClick={onOpenBookmarks}
          className="p-2 text-amber-400 hover:text-amber-300 rounded-lg hover:bg-slate-800 transition-colors relative"
          title="Bookmarks & Saved Snippets"
        >
          <Bookmark className="w-5 h-5" />
          {bookmarks.length > 0 && (
            <span className="absolute -top-1 -right-1 bg-amber-500 text-slate-950 font-bold text-[10px] w-4 h-4 rounded-full flex items-center justify-center">
              {bookmarks.length}
            </span>
          )}
        </button>
      </div>
    );
  }

  return (
    <div className="w-72 bg-slate-900 border-r border-slate-800 flex flex-col h-full shrink-0 transition-all duration-200">
      {/* Sidebar Header */}
      <div className="p-3 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <MessageSquare className="w-4 h-4 text-indigo-400" />
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">Workspaces</span>
        </div>
        <div className="flex items-center space-x-1">
          <button
            onClick={() => setIsCollapsed(true)}
            className="p-1.5 text-slate-400 hover:text-slate-200 rounded hover:bg-slate-800 transition-colors"
            title="Collapse Sidebar"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* New Conversation Button */}
      <div className="p-3 space-y-2">
        <button
          onClick={onNewThread}
          disabled={isLoading}
          className="w-full flex items-center justify-center space-x-2 px-3 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors shadow-sm"
        >
          <Plus className="w-4 h-4" />
          <span>New Conversation</span>
        </button>

        {/* Bookmarks Bar */}
        <button
          onClick={onOpenBookmarks}
          className="w-full flex items-center justify-between px-3 py-2 bg-slate-800/80 hover:bg-slate-800 border border-slate-700/60 text-slate-200 rounded-lg text-xs font-medium transition-colors"
        >
          <div className="flex items-center space-x-2">
            <Bookmark className="w-3.5 h-3.5 text-amber-400 fill-amber-400/20" />
            <span>Saved Snippets</span>
          </div>
          <span className="bg-amber-400/20 text-amber-300 px-1.5 py-0.5 rounded text-[11px] font-semibold">
            {bookmarks.length}
          </span>
        </button>
      </div>

      {/* Filter Tabs: Active vs Archived */}
      <div className="px-3 pt-1 pb-2 flex items-center justify-between border-b border-slate-800/60 text-xs">
        <div className="flex space-x-1">
          <button
            onClick={() => setShowArchived(false)}
            className={`px-2 py-1 rounded transition-colors ${
              !showArchived ? 'bg-slate-800 text-indigo-400 font-medium' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Active
          </button>
          <button
            onClick={() => setShowArchived(true)}
            className={`px-2 py-1 rounded transition-colors ${
              showArchived ? 'bg-slate-800 text-indigo-400 font-medium' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Archived
          </button>
        </div>
        <span className="text-[11px] text-slate-500">{filteredThreads.length}</span>
      </div>

      {/* Threads List */}
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1">
        {filteredThreads.length === 0 ? (
          <div className="text-center py-8 text-xs text-slate-500">
            {showArchived ? 'No archived conversations' : 'No active conversations'}
          </div>
        ) : (
          filteredThreads.map((thread) => {
            const isActive = thread.id === activeThreadId;
            const isEditing = thread.id === editingThreadId;
            const isDeleting = thread.id === deleteConfirmId;

            return (
              <div
                key={thread.id}
                onClick={() => onSelectThread(thread.id)}
                className={`group relative flex items-center justify-between p-2 rounded-lg cursor-pointer transition-colors text-xs ${
                  isActive
                    ? 'bg-slate-800 text-white border border-indigo-500/30'
                    : 'text-slate-300 hover:bg-slate-800/60 border border-transparent'
                }`}
              >
                <div className="flex-1 min-w-0 pr-2">
                  {isEditing ? (
                    <form
                      onSubmit={(e) => handleSaveRename(thread.id, e)}
                      onClick={(e) => e.stopPropagation()}
                      className="flex items-center space-x-1"
                    >
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        autoFocus
                        className="w-full bg-slate-950 border border-indigo-500 text-white rounded px-1.5 py-0.5 text-xs focus:outline-none"
                      />
                      <button
                        type="submit"
                        className="text-emerald-400 hover:text-emerald-300 p-0.5"
                        title="Save Title"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={handleCancelRename}
                        className="text-slate-400 hover:text-slate-300 p-0.5"
                        title="Cancel"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </form>
                  ) : (
                    <>
                      <div className="font-medium truncate text-slate-200">{thread.title}</div>
                      <div className="flex items-center space-x-2 text-[10px] text-slate-400 mt-0.5">
                        <span className="flex items-center space-x-0.5">
                          <Clock className="w-2.5 h-2.5" />
                          <span>{formatDate(thread.updated_at)}</span>
                        </span>
                        <span>•</span>
                        <span>{thread.message_count} msgs</span>
                      </div>
                    </>
                  )}
                </div>

                {/* Actions (visible on hover or active) */}
                {!isEditing && (
                  <div
                    onClick={(e) => e.stopPropagation()}
                    className={`flex items-center space-x-1 ${
                      isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                    } transition-opacity`}
                  >
                    {isDeleting ? (
                      <div className="flex items-center space-x-1 bg-red-950/80 px-1 py-0.5 rounded border border-red-800">
                        <button
                          onClick={() => {
                            onDeleteThread(thread.id);
                            setDeleteConfirmId(null);
                          }}
                          className="text-red-400 hover:text-red-200 text-[10px] font-bold px-1"
                          title="Confirm Delete"
                        >
                          Delete
                        </button>
                        <button
                          onClick={() => setDeleteConfirmId(null)}
                          className="text-slate-400 hover:text-slate-200"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    ) : (
                      <>
                        <button
                          onClick={(e) => handleStartRename(thread, e)}
                          className="p-1 text-slate-400 hover:text-slate-200 rounded hover:bg-slate-700/60"
                          title="Rename Thread"
                        >
                          <Edit2 className="w-3 h-3" />
                        </button>
                        <button
                          onClick={() => onArchiveToggle(thread.id, thread.is_archived)}
                          className="p-1 text-slate-400 hover:text-slate-200 rounded hover:bg-slate-700/60"
                          title={thread.is_archived ? 'Unarchive' : 'Archive'}
                        >
                          {thread.is_archived ? (
                            <RotateCcw className="w-3 h-3" />
                          ) : (
                            <Archive className="w-3 h-3" />
                          )}
                        </button>
                        <button
                          onClick={() => setDeleteConfirmId(thread.id)}
                          className="p-1 text-slate-400 hover:text-red-400 rounded hover:bg-slate-700/60"
                          title="Delete Thread"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

