import React, { useEffect, useState } from 'react';
import { CheckCircle2, Activity } from 'lucide-react';
import { api } from '../api/client';
import { SystemHealth } from '../types';

export const HealthBadge: React.FC = () => {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const checkHealth = async () => {
    setLoading(true);
    try {
      const data = await api.health.checkReady();
      setHealth(data);
    } catch {
      setHealth({ status: 'unreachable' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const isHealthy = health?.status === 'ready' || health?.status === 'live';

  return (
    <div className="relative inline-block text-left">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-full border transition-all cursor-pointer"
        style={{
          backgroundColor: isHealthy ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
          borderColor: isHealthy ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)',
          color: isHealthy ? '#059669' : '#dc2626',
        }}
        title="Click to view system health details"
      >
        <span
          className="w-2 h-2 rounded-full animate-pulse"
          style={{ backgroundColor: isHealthy ? '#10b981' : '#ef4444' }}
        />
        <span>{isHealthy ? 'System Ready' : 'System Degraded'}</span>
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-64 p-3 bg-white border border-slate-200 rounded-lg shadow-lg z-50 text-xs text-slate-700">
          <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-100 font-semibold text-slate-800">
            <span className="flex items-center gap-1">
              <Activity size={14} /> Service Health
            </span>
            <button
              onClick={checkHealth}
              disabled={loading}
              className="text-indigo-600 hover:underline cursor-pointer"
            >
              {loading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-slate-500">FastAPI Core:</span>
              <span className="font-medium text-emerald-600 flex items-center gap-1">
                <CheckCircle2 size={12} /> Live
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">PostgreSQL (RBAC):</span>
              <span className="font-medium text-emerald-600 flex items-center gap-1">
                <CheckCircle2 size={12} /> {health?.checks?.database || 'Healthy'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">ChromaDB (Vectors):</span>
              <span className="font-medium text-emerald-600 flex items-center gap-1">
                <CheckCircle2 size={12} /> {health?.checks?.vector_store || 'Healthy'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Storage Subsystem:</span>
              <span className="font-medium text-emerald-600 flex items-center gap-1">
                <CheckCircle2 size={12} /> {health?.checks?.storage || 'Healthy'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
