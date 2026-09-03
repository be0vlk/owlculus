// @vitest-environment node

import { describe, expect, it } from 'vitest'
import viteConfig from '../../../vite.config'

describe('Vite development server', () => {
  it('proxies same-origin API and WebSocket traffic to the local backend', () => {
    expect(viteConfig.server.cors).toBe(false)
    expect(viteConfig.server.proxy).toMatchObject({
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    })
  })
})
