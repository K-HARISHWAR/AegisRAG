import React, { useState } from 'react';
import { AuthProvider, useAuth } from './auth/AuthContext';
import { Navbar } from './components/Navbar';
import { LoginPage } from './pages/LoginPage';
import { ChatPage } from './pages/ChatPage';
import { DocumentsPage } from './pages/DocumentsPage';
import { AdminPage } from './pages/AdminPage';

const AppContent: React.FC = () => {
  const { isAuthenticated, isLoading, isAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState<'chat' | 'documents' | 'admin'>('chat');

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center text-white">
        <span className="w-8 h-8 border-3 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-xs text-slate-400">Authenticating AegisRAG RBAC Identity...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage onLoginSuccess={() => setActiveTab('chat')} />;
  }

  const handleSelectTab = (tab: 'chat' | 'documents' | 'admin') => {
    if (tab === 'admin' && !isAdmin) {
      setActiveTab('chat');
    } else {
      setActiveTab(tab);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Navbar activeTab={activeTab} onSelectTab={handleSelectTab} />
      <main className="flex-1">
        {activeTab === 'chat' && <ChatPage />}
        {activeTab === 'documents' && <DocumentsPage />}
        {activeTab === 'admin' && <AdminPage />}
      </main>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

export default App;

