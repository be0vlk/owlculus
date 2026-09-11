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

  it('uses the public auth client for setup without persisting authentication', async () => {
    localStorage.clear()
    const { authService } = await import('../auth')
    const administrator = {
      setup_token: 'server-token',
      username: 'owl_admin',
      email: 'admin@example.com',
      password: 'long-password',
    }

    await authService.getSetupStatus()
    await authService.createAdministrator(administrator)

    expect(axiosMock.instances).toHaveLength(1)
    expect(axiosMock.instances[0].get).toHaveBeenCalledWith('/api/auth/setup-status')
    expect(axiosMock.instances[0].post).toHaveBeenCalledWith('/api/users/', administrator)
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('token_type')).toBeNull()
  })

  it('posts client creation to the canonical collection URL without a redirect', async () => {
    const { clientService } = await import('../client')
    const client = { name: 'Example client' }

    await clientService.createClient(client)

    const apiClient = axiosMock.instances.find(({ post }) => post.mock.calls.length > 0)
    expect(apiClient.post).toHaveBeenCalledWith('/api/clients/', client)
  })

  it('uses canonical collection URLs for redirect-sensitive API routes', async () => {
    const [{ userService }, { inviteService }, { pluginService }, { caseService }] =
      await Promise.all([
        import('../user'),
        import('../invite'),
        import('../plugin'),
        import('../case'),
      ])

    await userService.getUsers()
    await userService.createUser({ username: 'analyst' })
    await inviteService.getInvites()
    await inviteService.createInvite({ email: 'analyst@example.com' })
    await pluginService.listPlugins()
    await caseService.createCase({ title: 'Example case' })

    const getCalls = axiosMock.instances.flatMap(({ get }) => get.mock.calls)
    const postCalls = axiosMock.instances.flatMap(({ post }) => post.mock.calls)
    expect(getCalls).toContainEqual(['/api/users/'])
    expect(postCalls).toContainEqual(['/api/users/', { username: 'analyst' }])
    expect(getCalls).toContainEqual(['/api/invites/'])
    expect(postCalls).toContainEqual(['/api/invites/', { email: 'analyst@example.com' }])
    expect(getCalls).toContainEqual(['/api/plugins/'])
    expect(postCalls).toContainEqual(['/api/cases/', { title: 'Example case' }])
  })
})
