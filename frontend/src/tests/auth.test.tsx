import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { AuthProvider, useAuth } from '../auth/AuthContext';
import { api } from '../api/client';

vi.mock('../api/client', () => ({
  api: {
    auth: {
      login: vi.fn(),
      getMe: vi.fn(),
    },
    health: {
      checkReady: vi.fn().mockResolvedValue({ status: 'ready' }),
      checkLive: vi.fn().mockResolvedValue({ status: 'live' }),
    },
  },
}));

const TestConsumer: React.FC = () => {
  const { user, isAuthenticated, isAdmin, isManager, departmentName, login, logout } = useAuth();
  return (
    <div>
      <div data-testid="auth-status">{isAuthenticated ? 'authenticated' : 'unauthenticated'}</div>
      <div data-testid="user-email">{user?.email || 'no-user'}</div>
      <div data-testid="is-admin">{isAdmin ? 'true' : 'false'}</div>
      <div data-testid="is-manager">{isManager ? 'true' : 'false'}</div>
      <div data-testid="department-name">{departmentName}</div>
      <button
        onClick={() => login('alice@example.com', 'password123')}
        data-testid="login-btn"
      >
        Login
      </button>
      <button onClick={logout} data-testid="logout-btn">
        Logout
      </button>
    </div>
  );
};

describe('AuthContext and RBAC State', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('initializes as unauthenticated when no token is present', () => {
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    expect(screen.getByTestId('auth-status').textContent).toBe('unauthenticated');
    expect(screen.getByTestId('user-email').textContent).toBe('no-user');
  });

  it('updates state properly on successful login', async () => {
    const mockUser = {
      id: '11111111-1111-1111-1111-111111111111',
      email: 'alice@example.com',
      department_id: 'dept-1',
      department: { id: 'dept-1', name: 'Engineering' },
      roles: [{ id: 'role-1', name: 'employee' }],
      is_active: true,
      is_superuser: false,
      created_at: '2026-10-24T00:00:00Z',
    };

    (api.auth.login as any).mockResolvedValueOnce({
      access_token: 'fake-jwt-token',
      token_type: 'bearer',
      expires_in: 3600,
      user: mockUser,
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    fireEvent.click(screen.getByTestId('login-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('authenticated');
      expect(screen.getByTestId('user-email').textContent).toBe('alice@example.com');
      expect(screen.getByTestId('department-name').textContent).toBe('Engineering');
      expect(screen.getByTestId('is-admin').textContent).toBe('false');
      expect(screen.getByTestId('is-manager').textContent).toBe('false');
      expect(localStorage.getItem('aegis_token')).toBe('fake-jwt-token');
    });
  });

  it('clears session on logout', async () => {
    const mockUser = {
      id: '22222222-2222-2222-2222-222222222222',
      email: 'admin@example.com',
      department_id: null,
      department: null,
      roles: [{ id: 'role-admin', name: 'admin' }],
      is_active: true,
      is_superuser: true,
      created_at: '2026-10-24T00:00:00Z',
    };

    (api.auth.login as any).mockResolvedValueOnce({
      access_token: 'admin-jwt-token',
      token_type: 'bearer',
      expires_in: 3600,
      user: mockUser,
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    fireEvent.click(screen.getByTestId('login-btn'));
    await waitFor(() => {
      expect(screen.getByTestId('is-admin').textContent).toBe('true');
    });

    fireEvent.click(screen.getByTestId('logout-btn'));
    expect(screen.getByTestId('auth-status').textContent).toBe('unauthenticated');
    expect(localStorage.getItem('aegis_token')).toBeNull();
  });
});
