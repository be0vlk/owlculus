// @vitest-environment node

import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const frontendRoot = fileURLToPath(new URL('../../..', import.meta.url))

async function readFrontendFile(path) {
  return readFile(new URL(path, `file://${frontendRoot}/`), 'utf8')
}

async function readPackageMetadata() {
  const [packageJsonText, packageLockText] = await Promise.all([
    readFrontendFile('package.json'),
    readFrontendFile('package-lock.json'),
  ])

  return {
    packageJson: JSON.parse(packageJsonText),
    packageLock: JSON.parse(packageLockText),
  }
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
    const { packageJson, packageLock } = await readPackageMetadata()
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

  it('locks the stable Vuetify 4 runtime and its migration tooling', async () => {
    const { packageJson, packageLock } = await readPackageMetadata()

    expect(packageJson.dependencies.vuetify).toBe('4.2.0')
    expect(packageJson.devDependencies['vite-plugin-vuetify']).toBe('2.1.3')
    expect(packageJson.devDependencies['eslint-plugin-vuetify']).toBe('2.7.2')
    expect(packageLock.packages['node_modules/vuetify'].version).toBe('4.2.0')
    expect(packageLock.packages['node_modules/vite-plugin-vuetify'].version).toBe('2.1.3')
    expect(packageLock.packages['node_modules/eslint-plugin-vuetify'].version).toBe('2.7.2')
  })
})
