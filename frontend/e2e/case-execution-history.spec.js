import process from 'node:process'
import { expect, test } from '@playwright/test'

const cases = [1, 2].map((id) => ({
  id,
  case_number: `CASE-${id}`,
  title: id === 1 ? 'Domain investigation' : 'Other investigation',
  status: 'Open',
  created_at: '2026-01-01T00:00:00Z',
  users: [],
  notes: '<p>Saved case notes</p>',
}))
const plugin = (id, day, name = `Plugin ${id}`, caseId = 1) => ({
  id,
  case_id: caseId,
  plugin_name: name,
  status: 'completed',
  revision: 1,
  created_at: `2026-08-${String(day).padStart(2, '0')}T12:00:00Z`,
  parameters: {},
})
const hunt = (id, day, name = `Hunt ${id}`, caseId = 1) => ({
  id,
  case_id: caseId,
  hunt_id: id,
  hunt_display_name: name,
  hunt_category: 'domain',
  hunt: { id, display_name: name, category: 'domain' },
  status: 'completed',
  progress: 1,
  created_at: `2026-08-${String(day).padStart(2, '0')}T12:00:00Z`,
  initial_parameters: {},
  steps: [],
})
const plugins = [
  plugin(7, 28),
  plugin(6, 24),
  plugin(5, 18),
  plugin(4, 12),
  plugin(3, 6),
  plugin(2, 2),
]
const hunts = [hunt(7, 26), hunt(6, 20), hunt(5, 14), hunt(4, 8), hunt(3, 1)]

async function setup(page, { role = 'Admin', theme = 'light' } = {}) {
  const reads = []
  const writes = []
  const failures = { plugin: false, hunt: false }
  const history = { plugins: [...plugins], hunts: [...hunts] }
  await page.addInitScript(
    ({ theme }) => {
      localStorage.setItem('access_token', 'browser-fixture')
      localStorage.setItem('color-scheme', theme)
    },
    { theme },
  )
  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    if (request.method() !== 'GET') {
      writes.push({ method: request.method(), path })
      return route.fulfill({ status: 409, json: { detail: 'History must not write' } })
    }
    reads.push(path + url.search)
    let body = []
    if (path === '/api/auth/setup-status') body = { setup_required: false }
    else if (path === '/api/users/me') body = { id: 1, role, username: 'investigator' }
    else if (path === '/api/cases/') body = cases
    else if (/^\/api\/cases\/\d+$/.test(path))
      body = cases.find((item) => item.id === Number(path.split('/').pop()))
    else if (/\/entities\/99$/.test(path))
      return route.fulfill({ status: 404, json: { detail: 'Entity unavailable' } })
    else if (path.includes('/entities')) body = []
    else if (path.startsWith('/api/plugins/executions/case/')) {
      if (failures.plugin)
        return route.fulfill({ status: 503, json: { detail: 'Plugin source unavailable' } })
      const records = path.endsWith('/1')
        ? history.plugins
        : [plugin(70, 29, 'Other case plugin', 2)]
      const cursor = Number(url.searchParams.get('cursor') || 0)
      const remaining = records.filter((item) => cursor === 0 || item.id < cursor)
      const items = remaining.slice(0, 2)
      body = { items, next_cursor: remaining.length > 2 ? items.at(-1).id : null }
    } else if (/\/api\/hunts\/cases\/\d+\/executions/.test(path)) {
      if (failures.hunt)
        return route.fulfill({ status: 503, json: { detail: 'Hunt source unavailable' } })
      body = path.includes('/cases/1/') ? history.hunts : [hunt(70, 27, 'Other case hunt', 2)]
    } else if (/\/api\/plugins\/executions\/\d+\/results/.test(path)) {
      body = { items: [{ finding: 'Retained plugin finding' }], cursor: 1, next_cursor: null }
    } else if (/\/api\/plugins\/executions\/\d+$/.test(path))
      body = plugins.find((item) => item.id === Number(path.split('/').pop()))
    else if (/\/api\/hunts\/executions\/\d+$/.test(path))
      body = hunts.find((item) => item.id === Number(path.split('/').pop()))
    await route.fulfill({ json: body })
  })
  return { reads, writes, failures, history }
}

async function delayResponse(page, path, json) {
  let release
  let accepted
  let delivered
  const ready = new Promise((resolve) => {
    accepted = resolve
  })
  const gate = new Promise((resolve) => {
    release = resolve
  })
  const done = new Promise((resolve) => {
    delivered = resolve
  })
  await page.route(path, async (route) => {
    accepted()
    await gate
    try {
      await route.fulfill({ json })
    } finally {
      delivered()
    }
  })
  return { ready, release, done }
}

const runsTab = (page) => page.getByRole('tab', { name: 'Plugins & Hunts', exact: true })
const row = (page, name) => page.getByRole('row').filter({ hasText: name })

async function verifyHistoryKeyboardAndOverflow(page) {
  const dimensions = await page.evaluate(() => ({
    content: document.documentElement.scrollWidth,
    viewport: document.documentElement.clientWidth,
  }))
  expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport)
  await runsTab(page).focus()
  await expect(runsTab(page)).toBeInViewport()
  await runsTab(page).press('Enter')
  const view = page.getByRole('button', { name: 'View Plugin Plugin 7 execution #7', exact: true })
  await view.focus()
  await expect(view).toBeFocused()
  await expect(view).toBeInViewport()
  await view.press('Enter')
  await page.getByRole('button', { name: 'View retained results', exact: true }).press('Enter')
  await expect(page.getByRole('dialog', { name: 'Plugin results', exact: true })).toContainText(
    'Retained plugin finding',
  )
}

const evidenceChecks = { after: verifyHistoryKeyboardAndOverflow }

// Opt-in capture also runs against the pre-change UI with identical API data.
if (process.env.OWLCULUS_HISTORY_EVIDENCE) {
  for (const [width, height] of [
    [1440, 900],
    [1366, 768],
    [3440, 1440],
    [390, 844],
  ]) {
    for (const theme of ['light', 'dark']) {
      test(`evidence ${width} ${theme}`, async ({ page }) => {
        await page.setViewportSize({ width, height })
        await setup(page, { theme })
        const phase = process.env.OWLCULUS_HISTORY_EVIDENCE
        await page.goto(`/case/1?tab=${phase === 'before' ? 'hunts' : 'runs'}`)
        await expect(page.getByRole('combobox', { name: /^Active case:/ })).toHaveValue(
          'CASE-1 — Domain investigation (Open)',
        )
        await expect(page.getByText('Plugin 7', { exact: false }).first()).toBeVisible()
        await page.evaluate(() => document.fonts.ready)
        await page.evaluate(() => window.scrollTo(0, 0))
        await page.screenshot({
          path: `../.scratch/case-workspace-polish/evidence/execution-history/${phase}-${width}-${theme}.png`,
          fullPage: true,
          animations: 'disabled',
        })
        await evidenceChecks[phase]?.(page)
      })
    }
  }
}

test('mixed IDs open the right execution and interleaved cursor pages retain both histories', async ({
  page,
}) => {
  const state = await setup(page)
  await page.goto('/case/1?tab=runs')
  await expect(runsTab(page)).toHaveAttribute('aria-selected', 'true')
  await expect(row(page, 'Plugin 7')).toContainText('Plugin')
  await expect(row(page, 'Hunt 7')).toContainText('Hunt')
  await expect(page.getByRole('tab')).toHaveText([
    'Entities',
    'Evidence',
    'Notes',
    'Plugins & Hunts',
    'Tasks',
  ])
  await page.getByRole('button', { name: /Load more.*executions/i }).click()
  await expect(row(page, 'Plugin 4')).toBeVisible()
  await page.getByRole('button', { name: /Load more.*executions/i }).click()
  await expect(row(page, 'Plugin 2')).toBeVisible()
  await expect(row(page, 'Hunt 3')).toBeVisible()
  await page.getByRole('combobox', { name: 'Executions per page', exact: true }).press('ArrowDown')
  await page.getByRole('option', { name: '10', exact: true }).click()
  await expect(row(page, 'Hunt 3')).toHaveCount(0)
  await page.getByRole('button', { name: 'Next page', exact: true }).click()
  await expect(row(page, 'Hunt 3')).toBeVisible()
  await row(page, 'Hunt 3').getByRole('button').focus()
  await expect(row(page, 'Hunt 3').getByRole('button')).toBeFocused()
  await page.getByRole('combobox', { name: 'Executions per page', exact: true }).press('ArrowDown')
  await page.getByRole('option', { name: '25', exact: true }).click()
  await expect(page.getByRole('row').filter({ hasText: /(?:Plugin|Hunt) \d/ })).toHaveText([
    /Plugin 7/,
    /Hunt 7/,
    /Plugin 6/,
    /Hunt 6/,
    /Plugin 5/,
    /Hunt 5/,
    /Plugin 4/,
    /Hunt 4/,
    /Plugin 3/,
    /Plugin 2/,
    /Hunt 3/,
  ])
  expect(state.reads.filter((url) => url.includes('/plugins/executions/case/1'))).toEqual([
    '/api/plugins/executions/case/1?cursor=0',
    '/api/plugins/executions/case/1?cursor=6',
    '/api/plugins/executions/case/1?cursor=4',
  ])
  state.history.plugins.unshift(plugin(8, 30))
  await page.getByRole('button', { name: 'Refresh history', exact: true }).click()
  await expect(row(page, 'Plugin 8')).toBeVisible()
  await expect(row(page, 'Plugin 2')).toHaveCount(1)
  await expect(row(page, 'Hunt 3')).toHaveCount(1)
  await expect(page.getByRole('row').filter({ hasText: /(?:Plugin|Hunt) \d/ })).toHaveCount(12)
  await row(page, 'Plugin 7').getByRole('button').press('Enter')
  await page.getByRole('button', { name: 'View retained results', exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'Plugin results', exact: true })).toContainText(
    'Retained plugin finding',
  )
  await page.getByRole('button', { name: 'Close plugin results', exact: true }).click()
  await row(page, 'Hunt 7').getByRole('button').click()
  await expect(page).toHaveURL(/\/case\/1\/hunts\/execution\/7$/)
  await expect(page.getByText('Hunt 7', { exact: true }).first()).toBeVisible()
  expect(state.writes).toEqual([])
})

for (const source of ['plugin', 'hunt']) {
  const available = source === 'plugin' ? 'Hunt 7' : 'Plugin 7'
  const recovered = source === 'plugin' ? 'Plugin 7' : 'Hunt 7'
  test(`${source} failure preserves other history and independent retry restores it`, async ({
    page,
  }) => {
    const state = await setup(page)
    state.failures[source] = true
    await page.goto('/case/1?tab=runs')
    await expect(row(page, available)).toBeVisible()
    await expect(
      page
        .getByRole('alert')
        .filter({ hasText: `${source === 'plugin' ? 'Plugin' : 'Hunt'} source unavailable` }),
    ).toBeVisible()
    const otherReads = state.reads.filter((url) =>
      url.includes(source === 'plugin' ? '/hunts/cases/' : '/plugins/executions/case/'),
    ).length
    state.failures[source] = false
    await page.getByRole('button', { name: new RegExp(`Retry ${source}`, 'i') }).click()
    await expect(row(page, recovered)).toBeVisible()
    await expect(row(page, available)).toBeVisible()
    expect(
      state.reads.filter((url) =>
        url.includes(source === 'plugin' ? '/hunts/cases/' : '/plugins/executions/case/'),
      ),
    ).toHaveLength(otherReads)
    expect(state.writes).toEqual([])
  })
}

for (const tab of ['runs', 'plugin-runs', 'hunts']) {
  test(`direct ${tab} link canonicalizes without losing unrelated query or refresh state`, async ({
    page,
  }) => {
    const state = await setup(page)
    await page.goto('/cases')
    await expect(page.getByRole('combobox', { name: /^Active case:/ })).toBeVisible()
    await page.goto(`/case/1?tab=${tab}&marker=retained`)
    await expect(runsTab(page)).toHaveAttribute('aria-selected', 'true')
    await expect(page).toHaveURL(/\/case\/1\?tab=runs&marker=retained$/)
    await page.reload()
    await expect(runsTab(page)).toHaveAttribute('aria-selected', 'true')
    await expect(row(page, 'Plugin 7')).toBeVisible()
    await page.getByRole('link', { name: 'Browse Hunts', exact: true }).click()
    await expect(page).toHaveURL(/\/case\/1\/hunts$/)
    await page.goBack()
    await expect(runsTab(page)).toHaveAttribute('aria-selected', 'true')
    await page.goBack()
    await expect(page).toHaveURL(/\/cases$/)
    expect(state.writes).toEqual([])
  })
}

test('Analyst keeps plugin history but cannot read hunts or use a legacy hunt tab', async ({
  page,
}) => {
  const state = await setup(page, { role: 'Analyst' })
  await page.goto('/case/1?tab=plugin-runs')
  await expect(runsTab(page)).toHaveAttribute('aria-selected', 'true')
  await expect(row(page, 'Plugin 7')).toBeVisible()
  await expect(row(page, 'Hunt 7')).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Browse Hunts', exact: true })).toHaveCount(0)
  await page.goto('/case/1?tab=hunts&marker=retained')
  await expect(page.getByRole('tab', { name: 'Entities', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  expect(new URL(page.url()).searchParams.get('marker')).toBe('retained')
  expect(state.reads.filter((url) => url.startsWith('/api/hunts/'))).toEqual([])
  expect(state.writes).toEqual([])
})

test('same-case tabs retain note drafts and selected results without execution submission', async ({
  page,
}) => {
  const state = await setup(page)
  await page.goto('/case/1?tab=notes')
  await page.getByRole('button', { name: 'Edit Notes', exact: true }).click()
  const notes = page.getByRole('textbox', { name: 'Case notes', exact: true })
  await notes.fill('Unsent investigation draft')
  await runsTab(page).click()
  await row(page, 'Plugin 7').getByRole('button').click()
  await expect(
    page.getByRole('button', { name: 'View retained results', exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: /Refresh history/i }).click()
  await page.getByRole('tab', { name: 'Notes', exact: true }).click()
  await expect(notes).toContainText('Unsent investigation draft')
  await runsTab(page).click()
  await page.getByRole('button', { name: 'View retained results', exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'Plugin results', exact: true })).toContainText(
    'Retained plugin finding',
  )
  await page.getByRole('button', { name: 'Close plugin results', exact: true }).click()
  await page.reload()
  await expect(row(page, 'Plugin 7')).toBeVisible()
  expect(state.writes).toEqual([])
})

for (const source of ['plugin', 'hunt']) {
  const path =
    source === 'plugin' ? '**/api/plugins/executions/case/1?*' : '**/api/hunts/cases/1/executions'
  test(`case switch discards delayed ${source} history and clears entity references`, async ({
    page,
  }) => {
    const state = await setup(page)
    const { ready, release, done } = await delayResponse(
      page,
      path,
      source === 'plugin' ? { items: plugins, next_cursor: null } : hunts,
    )
    try {
      await page.goto('/case/1?tab=runs&entity=99&marker=retained')
      await ready
      await expect(
        page.getByRole('status').filter({ hasText: `Loading ${source} history…` }),
      ).toBeVisible()
      const switcher = page.getByRole('combobox', { name: /^Active case:/ })
      await switcher.press('ArrowDown')
      await page.getByRole('option', { name: /^CASE-2\b/ }).click()
      await expect(page).toHaveURL(/\/case\/2\?tab=runs&marker=retained$/)
      await expect(row(page, 'Other case plugin')).toBeVisible()
      await expect(row(page, 'Other case hunt')).toBeVisible()
      release()
      await done
      await page.unroute(path)
      await expect(row(page, 'Plugin 7')).toHaveCount(0)
      await expect(row(page, 'Hunt 7')).toHaveCount(0)
      await expect(row(page, 'Other case plugin')).toBeVisible()
      expect(state.writes).toEqual([])
    } finally {
      release()
    }
  })
}

test('loading an interleaved plugin batch from an older hunt page returns to the new records', async ({
  page,
}) => {
  const state = await setup(page)
  state.history.hunts.push(
    ...Array.from({ length: 15 }, (_, i) => hunt(100 + i, 1, `Archived hunt ${100 + i}`)),
  )
  await page.goto('/case/1?tab=runs')
  await expect(row(page, 'Plugin 7')).toBeVisible()
  await page.getByRole('combobox', { name: 'Executions per page', exact: true }).press('ArrowDown')
  await page.getByRole('option', { name: '10', exact: true }).click()
  await page.getByRole('button', { name: 'Next page', exact: true }).click()
  await expect(
    page.getByRole('button', { name: 'Page 2, Current page', exact: true }),
  ).toBeVisible()
  await expect(page.getByRole('row').filter({ hasText: 'Archived hunt' }).first()).toBeVisible()
  await page.getByRole('button', { name: 'Load more plugin executions', exact: true }).click()
  await expect(
    page.getByRole('button', { name: 'Page 1, Current page', exact: true }),
  ).toBeVisible()
  await expect(row(page, 'Plugin 5')).toBeVisible()
  await expect(page.getByRole('status').filter({ hasText: /Returned to page 1/i })).toBeVisible()
  expect(state.writes).toEqual([])
})

test('failed older plugin cursor retries the same boundary without erasing loaded records', async ({
  page,
}) => {
  const state = await setup(page)
  await page.goto('/case/1?tab=runs')
  await expect(row(page, 'Plugin 7')).toBeVisible()
  state.failures.plugin = true
  await page.getByRole('button', { name: 'Load more plugin executions', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Plugin source unavailable')
  await expect(row(page, 'Plugin 7')).toBeVisible()
  await expect(row(page, 'Hunt 3')).toBeVisible()
  state.failures.plugin = false
  await page.getByRole('button', { name: 'Retry plugin history', exact: true }).click()
  await expect(row(page, 'Plugin 5')).toBeVisible()
  expect(state.reads.filter((url) => url.includes('/plugins/executions/case/1'))).toEqual([
    '/api/plugins/executions/case/1?cursor=0',
    '/api/plugins/executions/case/1?cursor=6',
    '/api/plugins/executions/case/1?cursor=6',
  ])
  await expect(row(page, 'Plugin 7')).toHaveCount(1)
  await expect(row(page, 'Hunt 7')).toHaveCount(1)
  expect(state.writes).toEqual([])
})

for (const source of ['plugins', 'hunts']) {
  const available = source === 'plugins' ? 'Hunt 7' : 'Plugin 7'
  const label = source === 'plugins' ? 'plugin' : 'hunt'
  test(`empty ${source} source keeps the available history visible`, async ({ page }) => {
    const state = await setup(page)
    state.history[source] = []
    await page.goto('/case/1?tab=runs')
    await expect(row(page, available)).toBeVisible()
    await expect(
      page.getByText(`No ${label} executions for this case.`, { exact: true }),
    ).toBeVisible()
    expect(state.writes).toEqual([])
  })
}

test('delayed retained plugin results cannot appear after switching cases', async ({ page }) => {
  const state = await setup(page)
  const { ready, release, done } = await delayResponse(
    page,
    '**/api/plugins/executions/7/results?*',
    { items: [{ finding: 'Previous case private results' }], cursor: 1, next_cursor: null },
  )
  try {
    await page.goto('/case/1?tab=runs')
    await row(page, 'Plugin 7').getByRole('button').click()
    await ready
    await page.getByRole('combobox', { name: /^Active case:/ }).press('ArrowDown')
    await page.getByRole('option', { name: /^CASE-2\b/ }).click()
    await expect(row(page, 'Other case plugin')).toBeVisible()
    release()
    await done
    await expect(
      page.getByRole('region', { name: 'Selected plugin execution', exact: true }),
    ).toHaveCount(0)
    await expect(page.getByText('Previous case private results', { exact: true })).toHaveCount(0)
    await expect(
      page.getByRole('button', { name: 'View retained results', exact: true }),
    ).toHaveCount(0)
    expect(state.writes).toEqual([])
  } finally {
    release()
  }
})
