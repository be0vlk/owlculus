import { vi } from 'vitest'

export const authService = {
  getSetupStatus: vi.fn(),
  createAdministrator: vi.fn(),
  login: vi.fn(),
  getCurrentUser: vi.fn(),
  logout: vi.fn(),
  getCurrentToken: vi.fn(() => null),
  getTokenType: vi.fn(() => 'bearer'),
  isAuthenticated: vi.fn(() => false),
}
