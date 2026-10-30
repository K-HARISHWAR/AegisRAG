import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { CitationDrawer } from '../components/CitationDrawer';
import { Navbar } from '../components/Navbar';
import { AdminPage } from '../pages/AdminPage';
import { AuthProvider } from '../auth/AuthContext';

vi.mock('../api/client', () => ({
  api: {
    admin: {
      listUsers: vi.fn().mockResolvedValue([]),
      listAuditLogs: vi.fn().mockResolvedValue([]),
    },
    health: {
      checkReady: vi.fn().mockResolvedValue({ status: 'ready' }),
      checkLive: vi.fn().mockResolvedValue({ status: 'live' }),
    },
  },
}));

describe('CitationDrawer Component', () => {
  it('renders grounded citations with location and content hash provenance', () => {
    const mockCitations = [
      {
        document_id: 'doc-123',
        document_title: 'engineering_runbook.pdf',
        location: 'Page 3',
        content_hash: 'abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
        snippet: 'Execute sysctl net.core.bpf_jit_harden=2 on all production nodes.',
      },
    ];

    render(
      <CitationDrawer
        isOpen={true}
        onClose={vi.fn()}
        citations={mockCitations}
        queryText="What is the kernel hardening command?"
      />
    );

    expect(screen.getByText('engineering_runbook.pdf')).toBeInTheDocument();
    expect(screen.getByText('Page 3')).toBeInTheDocument();
    expect(
      screen.getByText('"Execute sysctl net.core.bpf_jit_harden=2 on all production nodes."')
    ).toBeInTheDocument();
    expect(screen.getByText(/Hash: abcdef1234567890/)).toBeInTheDocument();
  });

  it('does not render when isOpen is false', () => {
    const { container } = render(
      <CitationDrawer
        isOpen={false}
        onClose={vi.fn()}
        citations={[]}
      />
    );

    expect(container.firstChild).toBeNull();
  });
});

describe('AdminPage RBAC Guard', () => {
  it('shows access restriction message for non-admin users', () => {
    render(
      <AuthProvider>
        <AdminPage />
      </AuthProvider>
    );

    expect(screen.getByText('Access Restricted')).toBeInTheDocument();
    expect(
      screen.getByText('The Admin Console is strictly reserved for verified system administrators.')
    ).toBeInTheDocument();
  });
});
