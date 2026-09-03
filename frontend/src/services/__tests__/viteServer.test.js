// @vitest-environment node

import { readFile } from 'node:fs/promises'
import { beforeEach, describe, expect, it, vi } from 'vitest'

describe('Vite development server', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('proxies same-origin API and WebSocket traffic to the local backend', async () => {
    const { default: config } = await import('../../../vite.config')

    expect(config.server.host).toBe('0.0.0.0')
    expect(config.server.cors).toBe(false)
    expect(config.server.proxy).toMatchObject({
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        xfwd: true,
        ws: true,
      },
    })
  })

  it('lets a server-side environment setting target a containerized backend', async () => {
    vi.stubEnv('API_PROXY_TARGET', 'http://backend:8000')

    try {
      const { default: config } = await import('../../../vite.config')

      expect(config.server.proxy['/api'].target).toBe('http://backend:8000')
    } finally {
      vi.unstubAllEnvs()
    }
  })

  it('configures the development container to proxy to its backend service', async () => {
    const composeFile = await readFile(
      new URL('../../../../docker-compose.dev.yml', import.meta.url),
      'utf8',
    )

    expect(composeFile).toContain('API_PROXY_TARGET=http://backend:8000')
    expect(composeFile).toContain('FORWARDED_ALLOW_IPS: ${FORWARDED_ALLOW_IPS:-172.30.0.254}')
    expect(composeFile).toContain('ipv4_address: 172.30.0.254')
  })
})
