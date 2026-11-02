import React, { useState } from 'react';
import { X, ThumbsDown, MessageSquare, AlertCircle, CheckCircle2 } from 'lucide-react';
import { api } from '../api/client';
import { ChatMessage } from '../types';

interface FeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
  message: ChatMessage | null;
  onFeedbackSubmitted: (messageId: string, rating: 'negative') => void;
}

const FAILURE_TAGS: { id: string; label: string; description: string }[] = [
  { id: 'incorrect', label: 'Incorrect Facts', description: 'Answer contains factual inaccuracies or hallucinations' },
  { id: 'incomplete', label: 'Incomplete', description: 'Important facts or necessary steps are missing' },
  { id: 'outdated', label: 'Outdated Version', description: 'Reflects superseded policies or stale document versions' },
  { id: 'poor_citation', label: 'Citation Issue', description: 'Citations are missing, inaccurate, or poorly coordinates' },
  { id: 'irrelevant_retrieval', label: 'Irrelevant Context', description: 'Retrieved context passages do not match the question' },
  { id: 'access_issue', label: 'Unexpected Restriction', description: 'Authorized document was unexpectedly restricted or abstained' },
];

export const FeedbackModal: React.FC<FeedbackModalProps> = ({
  isOpen,
  onClose,
  message,
  onFeedbackSubmitted,
}) => {
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [comment, setComment] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen || !message) return null;

  const toggleTag = (tagId: string) => {
    setSelectedTags((prev) =>
      prev.includes(tagId) ? prev.filter((t) => t !== tagId) : [...prev, tagId]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      await api.feedback.submit({
        query_id: message.queryId || null,
        query_text: message.userQueryText || 'User Query',
        answer_text: message.text,
        rating: 'negative',
        reason_tags: selectedTags,
        comment: comment.trim() || null,
        model_version: message.modelVersion || 'mock-llm-v1',
        prompt_version: message.promptVersion || 'v1.0.0',
        retrieved_document_versions: message.retrievedDocumentVersions || {},
        evidence_level: message.evidenceLevel || null,
      });

      onFeedbackSubmitted(message.id, 'negative');
      onClose();
    } catch (err: any) {
      setError(err?.message || 'Failed to record response feedback. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 animate-fadeIn">
      <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-rose-100 text-rose-600 flex items-center justify-center">
              <ThumbsDown size={16} />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-800">Improve Assistant Accuracy</h3>
              <p className="text-[11px] text-slate-500">Your feedback creates a diagnostic review task for administrators</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 transition-colors cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-xl flex items-center gap-2 text-xs text-red-700">
              <AlertCircle size={14} className="shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-2">
              What issues occurred with this response? (Select all that apply)
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {FAILURE_TAGS.map((tag) => {
                const isSelected = selectedTags.includes(tag.id);
                return (
                  <button
                    key={tag.id}
                    type="button"
                    onClick={() => toggleTag(tag.id)}
                    className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-rose-50 border-rose-300 text-rose-800 shadow-xs'
                        : 'bg-white border-slate-200 hover:border-slate-300 text-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-xs font-semibold">{tag.label}</span>
                      {isSelected && <CheckCircle2 size={12} className="text-rose-600" />}
                    </div>
                    <p className="text-[10px] text-slate-500 line-clamp-1">{tag.description}</p>
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1.5">
              <MessageSquare size={13} className="text-slate-400" />
              Additional Details (Optional)
            </label>
            <textarea
              rows={3}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Explain how the answer was incorrect, or what documentation is missing..."
              className="w-full p-2.5 text-xs rounded-xl border border-slate-300 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-800 placeholder-slate-400"
            />
          </div>

          <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
            <span>Model: {message.modelVersion || 'default'}</span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                disabled={isSubmitting}
                className="px-3 py-1.5 rounded-lg border border-slate-200 font-semibold text-slate-600 hover:bg-slate-50 transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="px-4 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-semibold shadow-xs transition-colors cursor-pointer disabled:opacity-50"
              >
                {isSubmitting ? 'Submitting...' : 'Submit Feedback'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

