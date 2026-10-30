import React, { useState } from 'react';
import { Shield, Lock, Mail, ArrowRight, AlertCircle, Users } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';

interface LoginPageProps {
  onLoginSuccess?: () => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onLoginSuccess }) => {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const personas = [
    {
      name: 'Alice Smith',
      email: 'alice@example.com',
      password: 'TestPass123!',
      dept: 'Engineering',
      role: 'Employee',
      color: 'border-blue-200 hover:border-blue-400 bg-blue-50/50',
      badge: 'bg-blue-100 text-blue-800',
    },
    {
      name: 'Charlie Brown',
      email: 'charlie@example.com',
      password: 'TestPass123!',
      dept: 'Engineering',
      role: 'Manager',
      color: 'border-emerald-200 hover:border-emerald-400 bg-emerald-50/50',
      badge: 'bg-emerald-100 text-emerald-800',
    },
    {
      name: 'Diana Prince',
      email: 'diana@example.com',
      password: 'TestPass123!',
      dept: 'HR',
      role: 'Manager',
      color: 'border-purple-200 hover:border-purple-400 bg-purple-50/50',
      badge: 'bg-purple-100 text-purple-800',
    },
    {
      name: 'Bob Jones',
      email: 'bob@example.com',
      password: 'TestPass123!',
      dept: 'HR',
      role: 'Employee',
      color: 'border-indigo-200 hover:border-indigo-400 bg-indigo-50/50',
      badge: 'bg-indigo-100 text-indigo-800',
    },
    {
      name: 'System Admin',
      email: 'admin@example.com',
      password: 'TestPass123!',
      dept: 'Global',
      role: 'Admin',
      color: 'border-red-200 hover:border-red-400 bg-red-50/50',
      badge: 'bg-red-100 text-red-800',
    },
  ];

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please provide both email and password.');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await login(email, password);
      onLoginSuccess?.();
    } catch (err: any) {
      setError(err?.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSelectPersona = (p: (typeof personas)[0]) => {
    setEmail(p.email);
    setPassword(p.password);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="inline-flex p-3 rounded-2xl bg-indigo-600 text-white shadow-xl mb-3">
          <Shield size={36} />
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-white">
          Aegis<span className="text-indigo-400">RAG</span>
        </h1>
        <p className="mt-1 text-xs text-slate-400">
          Server-Verified RBAC Document Assistant & Retrieval Guard
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <div className="bg-white py-8 px-6 shadow-2xl rounded-2xl sm:px-10 border border-slate-100">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-center gap-2">
              <AlertCircle size={16} className="shrink-0 text-red-500" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Corporate Email
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Mail size={16} />
                </div>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  className="w-full pl-9 pr-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  disabled={isSubmitting}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Lock size={16} />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full pl-9 pr-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  disabled={isSubmitting}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-2.5 px-4 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-xs transition-colors flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Verifying RBAC Identity...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight size={14} />
                </>
              )}
            </button>
          </form>

          {/* Quick Persona Switcher for Testing */}
          <div className="mt-6 pt-6 border-t border-slate-100">
            <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
              <Users size={14} />
              <span>Select Demo Persona (Click to fill)</span>
            </div>

            <div className="space-y-1.5">
              {personas.map((p) => (
                <button
                  key={p.email}
                  type="button"
                  onClick={() => handleSelectPersona(p)}
                  className={`w-full p-2 rounded-lg border text-left transition-all flex items-center justify-between cursor-pointer ${p.color}`}
                >
                  <div className="flex flex-col">
                    <span className="text-xs font-semibold text-slate-800">{p.name}</span>
                    <span className="text-[11px] text-slate-500">{p.email}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="text-[10px] text-slate-500 font-medium">{p.dept}</span>
                    <span className={`px-1.5 py-0.5 text-[10px] font-semibold rounded ${p.badge}`}>
                      {p.role}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        <p className="mt-4 text-center text-xs text-slate-400">
          Enforces server-side PostgreSQL role & department isolation.
        </p>
      </div>
    </div>
  );
};
