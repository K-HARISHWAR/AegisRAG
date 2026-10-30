import React from 'react';
import { Shield, MessageSquare, Files, Settings, LogOut, User as UserIcon } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { HealthBadge } from './HealthBadge';

interface NavbarProps {
  activeTab: 'chat' | 'documents' | 'admin';
  onSelectTab: (tab: 'chat' | 'documents' | 'admin') => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, onSelectTab }) => {
  const { user, isAdmin, departmentName, primaryRole, logout } = useAuth();

  const getDeptColor = (dept: string) => {
    if (dept.toLowerCase().includes('eng')) {
      return 'bg-blue-50 text-blue-700 border-blue-200';
    }
    if (dept.toLowerCase().includes('hr')) {
      return 'bg-purple-50 text-purple-700 border-purple-200';
    }
    return 'bg-slate-100 text-slate-700 border-slate-200';
  };

  const getRoleColor = (role: string) => {
    if (role === 'Admin') {
      return 'bg-red-50 text-red-700 border-red-200';
    }
    if (role === 'Department Manager') {
      return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    }
    return 'bg-slate-100 text-slate-600 border-slate-200';
  };

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-40 shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Navigation */}
          <div className="flex items-center gap-8">
            <div
              onClick={() => onSelectTab('chat')}
              className="flex items-center gap-2 cursor-pointer group"
            >
              <div className="p-2 rounded-lg bg-indigo-600 text-white shadow-xs group-hover:bg-indigo-700 transition-colors">
                <Shield size={20} />
              </div>
              <div>
                <span className="font-bold text-slate-900 text-base tracking-tight flex items-center gap-1">
                  Aegis<span className="text-indigo-600">RAG</span>
                </span>
                <span className="block text-[10px] text-slate-400 font-medium uppercase tracking-wider -mt-1">
                  Enterprise Assistant
                </span>
              </div>
            </div>

            {/* Navigation Tabs */}
            <nav className="flex items-center gap-1">
              <button
                onClick={() => onSelectTab('chat')}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'chat'
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                }`}
              >
                <MessageSquare size={16} />
                <span>Assistant</span>
              </button>

              <button
                onClick={() => onSelectTab('documents')}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'documents'
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                }`}
              >
                <Files size={16} />
                <span>Documents</span>
              </button>

              {isAdmin && (
                <button
                  onClick={() => onSelectTab('admin')}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                    activeTab === 'admin'
                      ? 'bg-indigo-50 text-indigo-700'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  <Settings size={16} />
                  <span>Admin Console</span>
                </button>
              )}
            </nav>
          </div>

          {/* Right Section: System Health + User Profile + Logout */}
          <div className="flex items-center gap-3">
            <HealthBadge />

            <div className="h-4 w-px bg-slate-200" />

            {/* User Info */}
            <div className="flex items-center gap-2.5">
              <div className="flex flex-col items-end">
                <span className="text-xs font-semibold text-slate-800 leading-tight">
                  {user?.email}
                </span>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span
                    className={`px-1.5 py-0.5 text-[10px] font-medium border rounded ${getDeptColor(
                      departmentName
                    )}`}
                  >
                    {departmentName}
                  </span>
                  <span
                    className={`px-1.5 py-0.5 text-[10px] font-semibold border rounded ${getRoleColor(
                      primaryRole
                    )}`}
                  >
                    {primaryRole}
                  </span>
                </div>
              </div>

              <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center font-bold text-xs">
                {user?.email?.charAt(0).toUpperCase() || <UserIcon size={14} />}
              </div>

              <button
                onClick={logout}
                className="p-1.5 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors cursor-pointer"
                title="Sign out"
              >
                <LogOut size={16} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

