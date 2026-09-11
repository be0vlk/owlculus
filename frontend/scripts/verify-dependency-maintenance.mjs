import assert from 'node:assert/strict'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'
import { ESLint } from 'eslint'
import watcher from '@parcel/watcher'
import * as sass from 'sass'
import { isVue2, isVue3, version } from 'vue-demi'

// Exercise rules against invalid examples, without writing fixtures into the source tree.
const eslint = new ESLint({ cwd: path.resolve(import.meta.dirname, '..') })
const probes = [
  ['src/maintenance-probe.js', 'unknownMaintenanceGlobal()', 'no-undef'],
  ['src/maintenance-probe.mjs', 'unknownMaintenanceGlobal()', 'no-undef'],
  ['src/maintenance-probe.jsx', 'const unused = 1', 'no-unused-vars'],
  [
    'src/components/MaintenanceProbe.vue',
    '<template><div v-if="true" v-else /></template>',
    'vue/valid-v-else',
  ],
  [
    'src/components/MaintenanceProbe.vue',
    '<template><v-btn flat /></template>',
    'vuetify/no-deprecated-props',
  ],
  [
    'src/components/MaintenanceProbe.vue',
    '<template><div class="text-h1">Heading</div></template>',
    'vuetify/no-deprecated-typography',
  ],
  [
    'src/stores/__tests__/maintenance.test.js',
    "import { expect, it } from 'vitest'; it('probe', () => { expect(1) })",
    'vitest/valid-expect',
  ],
  [
    'e2e/maintenance.spec.js',
    "import { test } from '@playwright/test'; test('probe', async ({ page }) => { await page.waitForTimeout(10) })",
    'playwright/no-wait-for-timeout',
  ],
]
for (const [filePath, source, rule] of probes) {
  const [result] = await eslint.lintText(source, { filePath })
  assert.ok(
    result.messages.some((message) => message.ruleId === rule),
    `${filePath}: ${rule}`,
  )
}
for (const filePath of ['src/maintenance-probe.js', 'src/components/MaintenanceProbe.vue']) {
  const config = await eslint.calculateConfigForFile(filePath)
  assert.ok(
    !Object.keys(config.rules).some(
      (rule) => rule.startsWith('vitest/') || rule.startsWith('playwright/'),
    ),
  )
}
for (const directory of ['dist', 'dist-ssr', 'coverage']) {
  assert.ok(await eslint.isPathIgnored(`${directory}/maintenance-probe.js`))
}
const [formatting] = await eslint.lintText(
  'window.console.log("spacing" ) ;\nlocalStorage.getItem("key")',
  { filePath: 'src/maintenance-probe.js' },
)
assert.deepEqual(formatting.messages, [])
console.log(
  'Lint probes passed: core, JSX, Vue, Vuetify, Vitest, Playwright, scopes, ignores, globals, formatting separation',
)

assert.equal(isVue3, true)
assert.equal(isVue2, false)
assert.match(version, /^3\./)
assert.match(sass.compileString('$color: red; .probe { color: $color; }').css, /color: red/)

// Watch real edits and compile their Sass contents using the installed native watcher.
const directory = await mkdtemp(path.join(tmpdir(), 'owlculus-maintenance-'))
const source = path.join(directory, 'probe.scss')
let subscription
try {
  await writeFile(source, '$color: red; .probe { color: $color; }')
  const events = []
  let watchError
  subscription = await watcher.subscribe(directory, (error, changes) => {
    watchError = error
    events.push(...changes)
  })
  for (const color of ['blue', 'green']) {
    events.length = 0
    await writeFile(source, `$color: ${color}; .probe { color: $color; }`)
    for (
      let attempt = 0;
      attempt < 100 && !events.some((event) => event.path === source);
      attempt++
    ) {
      await delay(50)
      if (watchError) throw watchError
    }
    assert.ok(
      events.some((event) => event.path === source && event.type === 'update'),
      `Missing ${color} update`,
    )
    assert.match(sass.compile(source).css, new RegExp(`color: ${color}`))
  }
  console.log(`Vue ${version}, Sass compilation, and two native watcher updates passed`)
} finally {
  await subscription?.unsubscribe()
  await rm(directory, { recursive: true, force: true })
}
