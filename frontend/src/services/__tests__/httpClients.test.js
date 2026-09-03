import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const axiosMock = vi.hoisted(() => ({
  create: vi.fn(),
  instances: [],
}))

vi.mock('axios', () => ({
  default: {
    create: axiosMock.create,
  },
}))

function createAxiosInstance(config) {
  const instance = {
    config,
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  }

  axiosMock.instances.push(instance)
  return instance
}

describe('browser HTTP clients', () => {
  beforeEach(() => {
    vi.resetModules()
    axiosMock.instances.length = 0
    axiosMock.create.mockReset()
    axiosMock.create.mockImplementation(createAxiosInstance)
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('uses relative /api paths when no API-base override is set', async () => {
    vi.stubEnv('VITE_API_BASE_URL', undefined)

    const [{ default: api }, { authService }] = await Promise.all([
      import('../api'),
      import('../auth'),
    ])

    await api.get('/api/cases/')
    await authService.login('admin', 'password')

    expect(axiosMock.instances).toHaveLength(2)
    expect(axiosMock.instances.every(({ config }) => config.baseURL === undefined)).toBe(true)

    const apiClient = axiosMock.instances.find(({ get }) => get.mock.calls.length > 0)
    const authClient = axiosMock.instances.find(({ post }) => post.mock.calls.length > 0)
    expect(apiClient.get).toHaveBeenCalledWith('/api/cases/')
    expect(authClient.post).toHaveBeenCalledWith(
      '/api/auth/login',
      expect.any(FormData),
      expect.any(Object),
    )
  })

  it('honors an explicit API-base override for development and tests', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.dev.example')

    await import('../api')

    expect(axiosMock.instances).toHaveLength(2)
    expect(
      axiosMock.instances.every(({ config }) => config.baseURL === 'https://api.dev.example'),
    ).toBe(true)
  })
})
