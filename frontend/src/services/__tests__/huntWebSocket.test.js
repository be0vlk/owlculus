import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const apiMock = vi.hoisted(() => ({
  post: vi.fn(),
}))

vi.mock('../api', () => ({
  default: apiMock,
}))

class WebSocketStub {
  static CONNECTING = 0
  static OPEN = 1
  close = vi.fn()

  constructor(url) {
    this.url = url
    this.readyState = 0
  }
}

describe('hunt execution streaming', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.stubGlobal('WebSocket', WebSocketStub)
    apiMock.post.mockResolvedValue({ data: { token: 'stream token' } })
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it.each([
    ['http:', '127.0.0.1:5173', 'ws://127.0.0.1:5173'],
    ['https:', 'owlculus.example:9443', 'wss://owlculus.example:9443'],
  ])(
    'uses the page host and matching WebSocket scheme for %s pages',
    async (protocol, host, expectedBaseUrl) => {
      vi.stubEnv('VITE_WS_BASE_URL', undefined)
      vi.stubGlobal('window', { location: { protocol, host } })
      const { huntService } = await import('../hunt')

      const stream = await huntService.createExecutionStream(42, vi.fn(), vi.fn())

      expect(stream.url).toBe(
        `${expectedBaseUrl}/api/hunts/executions/42/stream?token=stream%20token`,
      )
    },
  )

  it('honors an explicit WebSocket-base override for development and tests', async () => {
    vi.stubEnv('VITE_WS_BASE_URL', 'wss://socket.dev.example')
    vi.stubGlobal('window', {
      location: { protocol: 'http:', host: 'localhost:5173' },
    })
    const { huntService } = await import('../hunt')

    const stream = await huntService.createExecutionStream(7, vi.fn(), vi.fn())

    expect(stream.url).toBe(
      'wss://socket.dev.example/api/hunts/executions/7/stream?token=stream%20token',
    )
  })
})

it('closes a connecting stream when its case context is discarded', async () => {
  vi.stubGlobal('WebSocket', WebSocketStub)
  const { huntService } = await import('../hunt')
  const stream = new WebSocketStub('ws://localhost')
  huntService.closeExecutionStream(stream)
  expect(stream.close).toHaveBeenCalledOnce()
  vi.unstubAllGlobals()
})

it('sends a reconnect cursor and ignores duplicate or stale revisions', async () => {
  vi.stubGlobal('WebSocket', WebSocketStub)
  vi.stubGlobal('window', { location: { protocol: 'http:', host: 'localhost' } })
  apiMock.post.mockResolvedValue({ data: { token: 'once' } })
  const { huntService } = await import('../hunt')
  const messages = vi.fn()
  const stream = await huntService.createExecutionStream(7, messages, vi.fn(), '4-0')
  expect(stream.url).toContain('cursor=4-0')
  for (const revision of [5, 5, 3, 6]) {
    stream.onmessage({ data: JSON.stringify({ event_type: 'update', revision }) })
  }
  expect(messages.mock.calls.map(([event]) => event.revision)).toEqual([5, 6])
  huntService.closeExecutionStream(stream)
  vi.unstubAllGlobals()
})
