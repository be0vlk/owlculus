import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { webcrypto } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import process from 'node:process'

let storage, keys, sessions, OwlculusAPI, data, listeners
const A = 'https://a.example'
const B = 'https://b.example'
const reply = (body) => ({ ok: true, json: async () => body })
const deferred = () => {
  let resolve
  const promise = new Promise((done) => {
    resolve = done
  })
  return { promise, resolve }
}

beforeEach(async () => {
  vi.resetModules()
  vi.stubGlobal('crypto', webcrypto)
  data = {}
  listeners = []
  let queue = Promise.resolve()
  Object.defineProperty(navigator, 'locks', {
    configurable: true,
    value: {
      request: (_name, callback) => {
        const next = queue.then(callback)
        queue = next.catch(() => {})
        return next
      },
    },
  })
  vi.stubGlobal('chrome', {
    storage: {
      onChanged: { addListener: (fn) => listeners.push(fn) },
      local: {
        get: (names, cb) =>
          cb(
            Object.fromEntries(
              (names || Object.keys(data)).filter((k) => k in data).map((k) => [k, data[k]]),
            ),
          ),
        set: (values, cb) => {
          const changes = Object.fromEntries(
            Object.entries(values).map(([k, v]) => [k, { oldValue: data[k], newValue: v }]),
          )
          Object.assign(data, values)
          listeners.forEach((fn) => fn(changes, 'local'))
          cb?.()
        },
        remove: (names, cb) => {
          names.forEach((k) => delete data[k])
          cb()
        },
      },
    },
    permissions: { request: vi.fn().mockResolvedValue(true) },
    tabs: {
      query: vi.fn().mockResolvedValue([{ id: 1, title: 'Page', url: 'https://page.example' }]),
    },
    runtime: { openOptionsPage: vi.fn() },
  })
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url) => {
      const path = String(url)
      if (path.endsWith('/login'))
        return reply({ access_token: path.startsWith(A) ? 'token-a' : 'token-b' })
      if (path.endsWith('/me'))
        return reply({ username: path.startsWith(A) ? 'Alice' : 'Bob', role: 'Admin' })
      return reply([{ id: 1, title: 'A case', case_number: 'A-1' }])
    }),
  )
  const module = await import('../../../extension/utils/storage.js')
  storage = module.storage
  keys = module.CONFIG_KEYS
  sessions = await import('../../../extension/utils/session.js')
  ;({ OwlculusAPI } = await import('../../../extension/utils/api.js'))
  await storage.set({ [keys.API_ENDPOINT]: A })
})
afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

async function loginA() {
  const api = new OwlculusAPI()
  await api.login('alice', 'password')
  await sessions.updateSession(api.snapshot, { user: { username: 'Alice' }, lastCaseId: '1' })
  return api
}

it('switches A to B without sending A credentials and permits fresh B login', async () => {
  const stale = await loginA()
  await stale.getCases()
  expect(fetch.mock.calls.at(-1)[1].headers.get('Authorization')).toBe('bearer token-a')
  await sessions.selectEndpoint(B)
  expect((await sessions.readSession()).session).toBeNull()
  await expect(stale.getCases()).rejects.toThrow('changed')
  const fresh = new OwlculusAPI()
  await expect(fresh.getCases()).rejects.toThrow('sign in')
  await fresh.login('bob', 'password')
  expect(await fresh.getCurrentUser()).toMatchObject({ username: 'Bob' })
  const calls = fetch.mock.calls.filter(([url]) => String(url).startsWith(B))
  expect(calls.map(([, options]) => options.headers.get('Authorization'))).toEqual([
    null,
    'bearer token-b',
  ])
  expect((await readSession()).session.lastCaseId).toBeUndefined()
})

// Keep all storage access through the real encrypted adapter.
async function readSession() {
  return sessions.readSession()
}

it('rejects legacy credentials and externally edited endpoint settings', async () => {
  await storage.set({ [keys.AUTH_TOKEN]: 'legacy', [keys.USER_DATA]: { username: 'Alice' } })
  await expect(new OwlculusAPI().getCurrentUser()).rejects.toThrow('sign in')
  await loginA()
  await storage.set({ [keys.API_ENDPOINT]: B })
  await expect(new OwlculusAPI().getCases()).rejects.toThrow('sign in')
  expect(fetch).toHaveBeenCalledTimes(1)
})

it.each(['https://A.EXAMPLE:443/', '  https://a.example///  '])(
  'retains the session for equivalent endpoint %s',
  async (endpoint) => {
    const api = await loginA()
    await sessions.selectEndpoint(endpoint)
    expect((await readSession()).session.lastCaseId).toBe('1')
    await expect(api.getCurrentUser()).resolves.toMatchObject({ username: 'Alice' })
  },
)

it.each([
  'http://a.example',
  'https://a.example:444',
  'https://a.example/base',
  'https://a.example/Base',
])('signs out for distinct endpoint %s', async (endpoint) => {
  await loginA()
  await sessions.selectEndpoint(endpoint)
  expect((await readSession()).session).toBeNull()
})

it('normalizes base paths and rejects unsupported URL components before permission', async () => {
  expect(sessions.normalizeEndpoint('https://A.example:443/base/')).toBe(`${A}/base`)
  for (const value of [
    'file:///tmp',
    'https://user:pass@a.example',
    `${A}?x=1`,
    `${A}#fragment`,
    'invalid',
  ]) {
    await expect(sessions.selectEndpoint(value)).rejects.toThrow()
  }
  expect(globalThis.chrome.permissions.request).not.toHaveBeenCalled()
})

it('preserves selection, credentials, and Case when permission is denied', async () => {
  await loginA()
  const before = await readSession()
  globalThis.chrome.permissions.request.mockResolvedValue(false)
  await expect(sessions.selectEndpoint(B)).rejects.toThrow('Permission')
  expect(await readSession()).toEqual(before)
})

it('discards an old login even after switching A to B and back to A', async () => {
  const pending = deferred()
  const started = deferred()
  fetch.mockImplementationOnce(() => {
    started.resolve()
    return pending.promise
  })
  const login = new OwlculusAPI().login('alice', 'password')
  const rejected = login.catch((error) => error)
  await started.promise
  await sessions.selectEndpoint(B)
  await sessions.selectEndpoint(A)
  pending.resolve(reply({ access_token: 'late-a' }))
  expect((await rejected).message).toContain('changed')
  expect((await readSession()).session).toBeNull()
})

it('discards an old user response without overwriting a newer B session', async () => {
  const api = await loginA()
  const pending = deferred()
  const started = deferred()
  fetch.mockImplementationOnce(() => {
    started.resolve()
    return pending.promise
  })
  const user = api.getCurrentUser()
  const rejected = user.catch((error) => error)
  await started.promise
  await sessions.selectEndpoint(B)
  await new OwlculusAPI().login('bob', 'password')
  pending.resolve(reply({ username: 'Alice' }))
  expect((await rejected).message).toContain('changed')
  expect((await readSession()).session.token).toBe('token-b')
})

it('refreshes request credentials and rejects redirect/path escapes', async () => {
  await loginA()
  const api = new OwlculusAPI()
  await api.getCases()
  expect(fetch.mock.calls.at(-1)[1].redirect).toBe('error')
  await expect(api.request('/api/../../other')).rejects.toThrow('Invalid API')
  await sessions.selectEndpoint(B)
  await new OwlculusAPI().login('bob', 'password')
  await api.getCases()
  expect(fetch.mock.calls.at(-1)[1].headers.get('Authorization')).toBe('bearer token-b')
})

async function loadPage(name) {
  document.body.innerHTML = readFileSync(
    resolve(process.cwd(), `../extension/${name}/${name}.html`),
    'utf8',
  )
  const callbacks = []
  const original = document.addEventListener.bind(document)
  vi.spyOn(document, 'addEventListener').mockImplementation((event, cb, ...args) => {
    if (event === 'DOMContentLoaded') callbacks.push(cb)
    else original(event, cb, ...args)
  })
  await import(`../../../extension/${name}/${name}.js`)
  for (const callback of callbacks) await callback()
}

it('options retain authentication on permission denial and clear it on a switch', async () => {
  await loginA()
  await loadPage('options')
  expect(document.getElementById('current-user').textContent).toBe('Alice')
  globalThis.chrome.permissions.request.mockResolvedValue(false)
  const endpoint = document.getElementById('api-endpoint')
  endpoint.value = B
  endpoint.dispatchEvent(new Event('blur'))
  await vi.waitFor(() => expect(endpoint.value).toBe(A))
  expect(document.getElementById('auth-status').classList.contains('hidden')).toBe(false)
  globalThis.chrome.permissions.request.mockResolvedValue(true)
  endpoint.value = B
  endpoint.dispatchEvent(new Event('blur'))
  await vi.waitFor(() =>
    expect(document.getElementById('login-form').classList.contains('hidden')).toBe(false),
  )
  expect(document.getElementById('current-user').textContent).toBe('')
})

it('popup clears user and Case UI after an instance change', async () => {
  await loginA()
  await loadPage('popup')
  expect(document.getElementById('username').textContent).toBe('Alice')
  await sessions.selectEndpoint(B)
  expect(document.getElementById('capture-section').classList.contains('hidden')).toBe(true)
  expect(document.getElementById('username').textContent).toBe('')
  expect(document.getElementById('case-select').value).toBe('')
})

it('options login authenticates the selected instance and displays its user', async () => {
  await loadPage('options')
  document.getElementById('username').value = 'alice'
  document.getElementById('password').value = 'password'
  document.getElementById('login-btn').click()
  await vi.waitFor(() => expect(document.getElementById('current-user').textContent).toBe('Alice'))
  expect((await readSession()).session.user.username).toBe('Alice')
})

it('login pinned to a selection cannot send entered credentials after an instance switch', async () => {
  const selected = await sessions.selectEndpoint(A)
  await sessions.selectEndpoint(B)
  await expect(new OwlculusAPI(selected).login('alice', 'password')).rejects.toThrow('changed')
  expect(fetch).not.toHaveBeenCalled()
})

it.each(['options', 'popup'])(
  '%s rejects unbound legacy authentication in its UI',
  async (page) => {
    await storage.set({ [keys.AUTH_TOKEN]: 'legacy', [keys.USER_DATA]: { username: 'Alice' } })
    await loadPage(page)
    const id = page === 'options' ? 'login-form' : 'login-section'
    expect(document.getElementById(id).classList.contains('hidden')).toBe(false)
    expect(fetch).not.toHaveBeenCalled()
  },
)

it('options discard an older storage read after the selected instance changes', async () => {
  await loginA()
  const started = deferred()
  const release = deferred()
  const original = globalThis.chrome.storage.local.get
  vi.spyOn(globalThis.chrome.storage.local, 'get').mockImplementationOnce((names, callback) => {
    original(names, (result) => {
      started.resolve()
      release.promise.then(() => callback(result))
    })
  })
  const loading = loadPage('options')
  await started.promise
  await sessions.selectEndpoint(B)
  await vi.waitFor(() => expect(document.getElementById('api-endpoint').value).toBe(B))
  release.resolve()
  await loading
  expect(document.getElementById('api-endpoint').value).toBe(B)
  expect(document.getElementById('current-user').textContent).toBe('')
})

it('interleaved requests retain their own credentials and discard obsolete responses', async () => {
  await loginA()
  const api = new OwlculusAPI()
  const started = deferred()
  const pending = deferred()
  fetch.mockImplementationOnce(() => {
    started.resolve()
    return pending.promise
  })
  const oldRequest = api.getCases().catch((error) => error)
  await started.promise
  await sessions.selectEndpoint(B)
  await new OwlculusAPI().login('bob', 'password')
  await api.getCases()
  pending.resolve(reply([{ id: 99, title: 'Old A case' }]))
  expect((await oldRequest).message).toContain('changed')
  const caseCalls = fetch.mock.calls.filter(([url]) => String(url).endsWith('/cases/'))
  expect(
    caseCalls.map(([url, options]) => [String(url), options.headers.get('Authorization')]),
  ).toEqual([
    [`${A}/api/cases/`, 'bearer token-a'],
    [`${B}/api/cases/`, 'bearer token-b'],
  ])
})

it('a capture started in A cannot upload an old Case selection after fresh B login', async () => {
  await loginA()
  await loadPage('popup')
  const started = deferred()
  const pending = deferred()
  globalThis.chrome.tabs.sendMessage = vi.fn(() => {
    started.resolve()
    return pending.promise
  })
  document.getElementById('case-select').value = '1'
  document.getElementById('capture-btn').click()
  await started.promise
  await sessions.selectEndpoint(B)
  await new OwlculusAPI().login('bob', 'password')
  pending.resolve({ success: true, html: '<p>Captured page</p>' })
  await vi.waitFor(() => expect(document.getElementById('capture-btn').disabled).toBe(false))
  expect(fetch.mock.calls.some(([url]) => String(url).includes('/evidence/?'))).toBe(false)
})

it('options cannot restore A user when its final login check finishes after a B switch', async () => {
  await loadPage('options')
  const started = deferred()
  const release = deferred()
  const originalSet = globalThis.chrome.storage.local.set
  const originalGet = globalThis.chrome.storage.local.get
  vi.spyOn(globalThis.chrome.storage.local, 'set').mockImplementation((values, callback) => {
    // The real adapter writes the user cache separately from session establishment.
    if (Object.keys(values).length === 1 && values.enc_session) {
      vi.spyOn(globalThis.chrome.storage.local, 'get').mockImplementationOnce((names, done) => {
        originalGet(names, (result) => {
          started.resolve()
          release.promise.then(() => done(result))
        })
      })
    }
    originalSet(values, callback)
  })
  document.getElementById('username').value = 'alice'
  document.getElementById('password').value = 'password'
  document.getElementById('login-btn').click()
  await started.promise
  await sessions.selectEndpoint(B)
  await vi.waitFor(() => expect(document.getElementById('api-endpoint').value).toBe(B))
  release.resolve()
  await vi.waitFor(() => expect(document.getElementById('login-btn').disabled).toBe(false))
  expect(document.getElementById('current-user').textContent).toBe('')
  expect(document.getElementById('auth-status').classList.contains('hidden')).toBe(true)
})
