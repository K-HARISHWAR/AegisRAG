import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ChatPage } from '../pages/ChatPage';
import { AuthProvider } from '../auth/AuthContext';
import { api } from '../api/client';

vi.mock('../api/client', () => ({
  api: {
    chat: {
      query: vi.fn(),
    },
    health: {
      checkReady: vi.fn().mockResolvedValue({ status: 'ready' }),
      checkLive: vi.fn().mockResolvedValue({ status: 'live' }),
    },
  },
}));

describe('ChatPage Component', () => {
  it('renders grounded assistant response with citations on successful query', async () => {
    (api.chat.query as any).mockResolvedValueOnce({
      query: 'What is the server deployment checklist?',
      answer: 'The server deployment requires network validation and staging sync [Doc: engineering_runbook.pdf, Page 1].',
      citations: [
        {
          document_id: 'doc-eng-1',
          document_title: 'engineering_runbook.pdf',
          location: 'Page 1',
          content_hash: '1234567890abcdef',
          snippet: 'Pre-flight checks require staging sync and network validation.',
        },
      ],
      retrieved_chunks: [
        {
          chunk_id: 'chunk-1',
          document_id: 'doc-eng-1',
          document_title: 'engineering_runbook.pdf',
          location: 'Page 1',
          content_hash: '1234567890abcdef',
          text: 'Pre-flight checks require staging sync and network validation.',
          dense_score: 0.9,
          sparse_score: 0.85,
          combined_score: 0.032,
        },
      ],
      abstained: false,
      execution_time_ms: 450.5,
    });

    render(
      <AuthProvider>
        <ChatPage />
      </AuthProvider>
    );

    const input = screen.getByPlaceholderText(
      /Ask a question about internal procedures, runbooks, or policies.../i
    );
    fireEvent.change(input, { target: { value: 'What is the server deployment checklist?' } });

    const submitBtn = screen.getByTitle('Submit Query');
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/The server deployment requires network validation and staging sync/)
      ).toBeInTheDocument();
      expect(screen.getByText('engineering_runbook.pdf')).toBeInTheDocument();
      expect(screen.getByText('(Page 1)')).toBeInTheDocument();
    });
  });

  it('renders abstention banner when documentation is insufficient or unauthorized', async () => {
    (api.chat.query as any).mockResolvedValueOnce({
      query: 'What are the executive salaries?',
      answer: 'The available documentation does not contain sufficient information to answer this question.',
      citations: [],
      retrieved_chunks: [],
      abstained: true,
      execution_time_ms: 120.0,
    });

    render(
      <AuthProvider>
        <ChatPage />
      </AuthProvider>
    );

    const input = screen.getByPlaceholderText(
      /Ask a question about internal procedures, runbooks, or policies.../i
    );
    fireEvent.change(input, { target: { value: 'What are the executive salaries?' } });

    const submitBtn = screen.getByTitle('Submit Query');
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('Insufficient Evidence / Access Restricted')).toBeInTheDocument();
      expect(
        screen.getByText(
          'The available documentation does not contain sufficient information to answer this question.'
        )
      ).toBeInTheDocument();
    });
  });
});

