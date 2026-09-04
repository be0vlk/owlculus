// @vitest-environment node

import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const frontendRoot = fileURLToPath(new URL('../../..', import.meta.url))

async function readFrontendFile(path) {
  return readFile(new URL(path, `file://${frontendRoot}/`), 'utf8')
}

describe('frontend runtime baseline', () => {
  it('declares Node 24 consistently for local, install, development, and production use', async () => {
    const [packageJsonText, npmConfig, nodeVersion, productionDockerfile, developmentDockerfile] =
      await Promise.all([
        readFrontendFile('package.json'),
        readFrontendFile('.npmrc'),
        readFrontendFile('.nvmrc'),
        readFile(`${frontendRoot}/Dockerfile`, 'utf8'),
        readFile(`${frontendRoot}/Dockerfile.dev`, 'utf8'),
      ])
    const packageJson = JSON.parse(packageJsonText)

    expect(packageJson.engines).toEqual({ node: '>=24 <25', npm: '>=11 <12' })
    expect(npmConfig).toMatch(/^engine-strict=true\s*$/)
    expect(nodeVersion.trim()).toBe('24')
    expect(productionDockerfile).toContain('FROM node:24-alpine AS frontend-builder')
    expect(developmentDockerfile).toContain('FROM node:24-alpine')
  })

  it('locks Vue and its runtime/compiler packages to the stable 3.5.42 release', async () => {
    const [packageJsonText, packageLockText] = await Promise.all([
      readFrontendFile('package.json'),
      readFrontendFile('package-lock.json'),
    ])
    const packageJson = JSON.parse(packageJsonText)
    const packageLock = JSON.parse(packageLockText)
    const vuePackages = [
      'vue',
      '@vue/compiler-core',
      '@vue/compiler-dom',
      '@vue/compiler-sfc',
      '@vue/compiler-ssr',
      '@vue/reactivity',
      '@vue/runtime-core',
      '@vue/runtime-dom',
      '@vue/server-renderer',
      '@vue/shared',
    ]

    expect(packageJson.dependencies.vue).toBe('3.5.42')
    expect(packageLock.packages[''].engines).toEqual(packageJson.engines)
    expect(
      vuePackages.map((packageName) => packageLock.packages[`node_modules/${packageName}`].version),
    ).toEqual(vuePackages.map(() => '3.5.42'))
  })
})
