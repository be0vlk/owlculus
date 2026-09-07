import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useClientsStore } from '../clients'
import { useAuthStore } from '../auth'
import { clientService } from '../../services/client'

vi.mock('../../services/client', () => ({ clientService: { getClients: vi.fn() } }))

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  vi.clearAllMocks()
  setActivePinia(createPinia())
  Object.assign(useAuthStore(), {
    isInitialized: true,
    isAuthenticated: true,
    user: { id: 1, role: 'Admin' },
  })
})

it('clears cached clients at logout and ignores the previous session’s pending response', async () => {
  const store = useClientsStore()
  clientService.getClients.mockResolvedValue([{ id: 9, name: 'Old session' }])
  await store.refresh()
  expect(store.clients).toHaveLength(1)

  let finish
  clientService.getClients.mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve
    }),
  )
  const pending = store.refresh()
  await useAuthStore().logout()
  expect(store.clients).toEqual([])

  Object.assign(useAuthStore(), { isAuthenticated: true, user: { id: 2, role: 'Admin' } })
  clientService.getClients.mockResolvedValue([{ id: 10, name: 'New session' }])
  await store.refresh()
  finish([{ id: 9, name: 'Old session' }])
  await pending
  expect(store.clients).toEqual([{ id: 10, name: 'New session' }])
})

it('clears cached clients when the user’s role changes', async () => {
  const store = useClientsStore()
  clientService.getClients.mockResolvedValue([{ id: 9, name: 'Acme' }])
  await store.refresh()
  useAuthStore().user.role = 'Investigator'
  expect(store.clients).toEqual([])
})

it('retains cached clients on a transient failure but clears them when access is denied', async () => {
  const store = useClientsStore()
  const clients = [{ id: 9, name: 'Acme' }]
  clientService.getClients.mockResolvedValue(clients)
  await store.refresh()

  clientService.getClients.mockRejectedValueOnce(new Error('Network unavailable'))
  await expect(store.refresh()).rejects.toThrow('Network unavailable')
  expect(store.clients).toEqual(clients)

  clientService.getClients.mockRejectedValueOnce({ response: { status: 403 } })
  await expect(store.refresh()).rejects.toEqual({ response: { status: 403 } })
  expect(store.clients).toEqual([])
})

it.each([
  [
    'creation',
    (store) => store.upsert({ id: 10, name: 'New client' }),
    [
      { id: 9, name: 'Acme' },
      { id: 10, name: 'New client' },
    ],
  ],
  [
    'edit',
    (store) => store.upsert({ id: 9, name: 'Updated Acme' }),
    [{ id: 9, name: 'Updated Acme' }],
  ],
  ['deletion', (store) => store.remove(9), []],
])(
  'does not overwrite a completed client %s with an older refresh',
  async (_name, applyChange, expected) => {
    const store = useClientsStore()
    const oldRows = [{ id: 9, name: 'Acme' }]
    clientService.getClients.mockResolvedValue(oldRows)
    await store.refresh()

    let finish
    clientService.getClients.mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve
      }),
    )
    const pending = store.refresh()
    applyChange(store)
    finish(oldRows)
    await pending
    expect(store.clients).toEqual(expected)
  },
)
