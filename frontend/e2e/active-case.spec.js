import { expect, test } from '@playwright/test'

const cases = [
  {
    id: 1,
    case_number: 'CASE-OLD',
    title: 'Older investigation',
    status: 'Closed',
    created_at: '2025-01-01T00:00:00Z',
    users: [],
    notes: '',
  },
  {
    id: 2,
    case_number: 'CASE-NEW',
    title: 'Newer investigation',
    status: 'Open',
    created_at: '2026-01-01T00:00:00Z',
    users: [],
    notes: '',
  },
]

// Disposable browser contexts and authorized API fixtures exercise the application
// shell and tool workflows without touching a developer database or external model.
async function setup(page, role = 'Admin', accessible = cases) {
  const caseRecords = accessible.map((item) => ({ ...item, users: [] }))
  await page.addInitScript(() => localStorage.setItem('access_token', 'browser-fixture'))
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    let body = []
    if (path === '/api/auth/setup-status') body = { setup_required: false }
    else if (path === '/api/users/me') body = { id: 1, role, username: 'investigator' }
    else if (path === '/api/clients/') body = [{ id: 1, name: 'Test client' }]
    else if (path === '/api/users/')
      body = [{ id: 2, role: 'Investigator', email: 'member@example.org', username: 'member' }]
    else if (path === '/api/cases/' && route.request().method() === 'POST') {
      body = {
        ...route.request().postDataJSON(),
        id: 3,
        case_number: 'CASE-CREATED',
        created_at: '2026-09-04T00:00:00Z',
        users: [],
        notes: '',
      }
      caseRecords.push(body)
    } else if (path === '/api/cases/') body = caseRecords
    else if (/^\/api\/cases\/\d+\/users\/2$/.test(path)) {
      const item = caseRecords.find((item) => item.id === Number(path.split('/')[3]))
      item.users = [
        { id: 2, email: 'member@example.org', username: 'member', role: 'Investigator' },
      ]
      body = item
    } else if (/^\/api\/cases\/\d+$/.test(path))
      body = caseRecords.find((item) => item.id === Number(path.split('/').pop()))
    else if (path.includes('/entities')) body = { items: [], total: 0, page: 1, size: 10, pages: 0 }
    await route.fulfill({ json: body })
  })
}

for (const viewport of [
  { width: 1440, height: 900 },
  { width: 390, height: 844 },
]) {
  test(`active case is visible, searchable by keyboard, and restored at ${viewport.width}px`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport)
    await setup(page)
    await page.goto('/cases')
    const switcher = page.getByRole('combobox', { name: 'Active case', exact: true })
    await expect(switcher).toBeVisible()
    await expect(switcher).toHaveValue('CASE-NEW — Newer investigation (Open)')
    await switcher.fill('CASE-OLD')
    await expect(
      page.getByRole('option', { name: 'CASE-OLD — Older investigation (Closed)', exact: true }),
    ).toBeVisible()
    await switcher.press('ArrowDown')
    await switcher.press('Enter')
    await expect(page).toHaveURL(/\/case\/1$/)
    await expect(page.getByRole('heading', { name: 'Case: CASE-OLD', exact: true })).toBeVisible()
    await expect(
      page.getByRole('status').filter({ hasText: 'Active case: CASE-OLD' }),
    ).toBeVisible()
    await page.getByRole('link', { name: 'Cases', exact: true }).click()
    await page.reload()
    await expect(switcher).toHaveValue('CASE-OLD — Older investigation (Closed)')
    await page.goto('/case/2?tab=notes')
    await expect(switcher).toHaveValue('CASE-NEW — Newer investigation (Open)')
    await switcher.fill('CASE-OLD')
    await expect(
      page.getByRole('option', { name: 'CASE-OLD — Older investigation (Closed)', exact: true }),
    ).toBeVisible()
    await switcher.press('ArrowDown')
    await switcher.press('Enter')
    await expect(page).toHaveURL(/\/case\/1\?tab=notes$/)
    await page.screenshot({ path: test.info().outputPath('active-case.png') })
  })
}

test('empty context explains disabled navigation and offers administrators a first case', async ({
  page,
}) => {
  await setup(page, 'Admin', [])
  await page.goto('/case/999')
  await expect(page).toHaveURL(/\/cases$/)
  await expect(page.getByRole('button', { name: 'Create First Case', exact: true })).toBeVisible()
  await expect(page.getByText('No accessible cases', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Create a case', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'New Case', exact: true })
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: 'Cancel', exact: true }).click()
  await page.getByRole('link', { name: 'Create a case', exact: true }).click()
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: 'Cancel', exact: true }).click()

  await expect(
    page.getByLabel('Plugins: No accessible case. Create a case or contact an administrator.'),
  ).toHaveAttribute('aria-disabled', 'true')
})

test('investigators with no cases receive assignment guidance', async ({ page }) => {
  await setup(page, 'Investigator', [])
  await page.goto('/cases')
  await expect(
    page.getByText('Contact an administrator to be assigned to a case.', { exact: true }).first(),
  ).toBeVisible()
  await expect(page.getByRole('button', { name: 'Create First Case', exact: true })).toHaveCount(0)
})

test('creating a case selects it and opens its overview', async ({ page }) => {
  await setup(page)
  await page.goto('/cases')
  await page.getByRole('button', { name: 'New Case', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'New Case', exact: true })
  await dialog.getByLabel('Title', { exact: true }).fill('Created investigation')
  await dialog.getByRole('button', { name: 'Create Case', exact: true }).click()
  await expect(page).toHaveURL(/\/case\/3$/)
  await expect(page.getByRole('combobox', { name: 'Active case', exact: true })).toHaveValue(
    'CASE-CREATED — Created investigation (Open)',
  )
  await page.getByRole('link', { name: 'Cases', exact: true }).click()
  await page.getByRole('cell', { name: 'Newer investigation', exact: true }).click()
  await expect(page).toHaveURL(/\/case\/2$/)
  await expect(page.getByRole('combobox', { name: 'Active case', exact: true })).toHaveValue(
    'CASE-NEW — Newer investigation (Open)',
  )
})

test('refreshes membership without closing the current workspace dialog', async ({ page }) => {
  await setup(page)
  await page.goto('/case/2')
  await page.getByRole('button', { name: 'Manage Users', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Manage Case Users', exact: true })
  await dialog.getByLabel('Select User', { exact: true }).press('ArrowDown')
  await page.getByRole('option', { name: /member@example.org/ }).click()
  await dialog.getByRole('button', { name: 'Add User', exact: true }).click()
  await expect(
    dialog.getByRole('button', { name: 'Remove member@example.org from case', exact: true }),
  ).toBeVisible()
  await dialog.getByRole('button', { name: 'Done', exact: true }).click()
})

test('switching workspaces drops the previous draft and saves notes to the URL case', async ({
  page,
}) => {
  await setup(page)
  await page.goto('/case/1?tab=notes')
  await page.getByRole('button', { name: 'Edit Notes', exact: true }).click()
  const notes = page.getByRole('textbox', { name: 'Case notes', exact: true })
  await notes.fill('Private draft for the older investigation')
  const switcher = page.getByRole('combobox', { name: 'Active case', exact: true })
  await switcher.fill('CASE-NEW')
  await expect(
    page.getByRole('option', { name: 'CASE-NEW — Newer investigation (Open)', exact: true }),
  ).toBeVisible()
  await switcher.press('ArrowDown')
  await switcher.press('Enter')
  await expect(page).toHaveURL(/\/case\/2\?tab=notes$/)
  await page.getByRole('button', { name: 'Edit Notes', exact: true }).click()
  await expect(notes).not.toContainText('Private draft')
  await notes.fill('Notes for the newer investigation')
  const saved = page.waitForRequest(
    (request) => request.method() === 'PUT' && new URL(request.url()).pathname === '/api/cases/2',
  )
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  expect((await saved).postDataJSON().notes).toContain('Notes for the newer investigation')
  await expect(page.getByRole('status').filter({ hasText: 'Notes saved' })).toBeVisible()
})

test('shows the authenticated shell loading state before any case is resolved', async ({
  page,
}) => {
  await setup(page)
  let release
  const pending = new Promise((resolve) => {
    release = resolve
  })
  await page.route('**/api/cases/?*', async (route) => {
    await pending
    await route.fulfill({ json: cases })
  })
  await page.goto('/cases')
  await expect(page.getByRole('status').filter({ hasText: 'Loading cases…' })).toBeVisible()
  release()
  await expect(page.getByRole('combobox', { name: 'Active case', exact: true })).toBeEnabled()
})

test('tasks remain scoped through creation, switching and legacy detail links', async ({
  page,
}) => {
  await setup(page)
  const tasks = [
    {
      id: 11,
      case_id: 1,
      title: 'Older task',
      description: 'Old evidence',
      status: 'completed',
      priority: 'medium',
      assigned_to: { id: 1 },
      assigned_by: { username: 'investigator' },
    },
    {
      id: 22,
      case_id: 2,
      title: 'Newer task',
      description: 'New evidence',
      status: 'not_started',
      priority: 'medium',
      assigned_to: { id: 1 },
      assigned_by: { username: 'investigator' },
    },
  ]
  const requestedCases = []
  const createdTasks = []
  await page.route('**/api/tasks/**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname === '/api/tasks/templates') return route.fulfill({ json: [] })
    if (route.request().method() === 'POST') {
      const data = route.request().postDataJSON()
      createdTasks.push(data)
      const task = { ...data, id: 23, status: 'not_started', assigned_to: { id: 1 } }
      tasks.push(task)
      return route.fulfill({ json: task })
    }
    if (url.pathname === '/api/tasks/') {
      const caseId = Number(url.searchParams.get('case_id'))
      requestedCases.push(caseId)
      return route.fulfill({ json: tasks.filter((task) => task.case_id === caseId) })
    }
    return route.fulfill({
      json: tasks.find((task) => task.id === Number(url.pathname.split('/').pop())),
    })
  })
  await page.goto('/tasks')
  await expect(page).toHaveURL(/\/case\/2\/tasks$/)
  await expect(page.getByRole('link', { name: 'Newer task', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Older task', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'New Task', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Create Task', exact: true })
  await expect(dialog.getByRole('combobox', { name: 'Case', exact: true })).toHaveCount(0)
  await dialog.getByRole('textbox', { name: 'Title', exact: true }).fill('Review new evidence')
  await dialog.getByRole('textbox', { name: 'Description', exact: true }).fill('Check source')
  await dialog.getByRole('button', { name: 'Create', exact: true }).click()
  await expect(dialog).toBeHidden()
  await expect(page.getByRole('link', { name: 'Review new evidence', exact: true })).toBeVisible()
  expect(createdTasks).toEqual([
    expect.objectContaining({ case_id: 2, title: 'Review new evidence' }),
  ])
  const switcher = page.getByRole('combobox', { name: 'Active case', exact: true })
  await switcher.fill('CASE-OLD')
  await page
    .getByRole('option', { name: 'CASE-OLD — Older investigation (Closed)', exact: true })
    .click()
  await expect(page).toHaveURL(/\/case\/1\/tasks$/)
  await expect(page.getByRole('link', { name: 'Older task', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Newer task', exact: true })).toHaveCount(0)
  expect(requestedCases).toContain(1)
  expect(requestedCases).toContain(2)
  expect(requestedCases).not.toContain(0)
  await page.goto('/tasks/22')
  await expect(page).toHaveURL(/\/case\/2\/tasks\/22$/)
  await expect(switcher).toHaveValue('CASE-NEW — Newer investigation (Open)')
  await expect(page.getByRole('heading', { name: 'Task: Newer task', exact: true })).toBeVisible()
})

test('hunts execute in the active case and legacy execution links restore their owner', async ({
  page,
}) => {
  await setup(page)
  const hunt = {
    id: 7,
    display_name: 'Context Hunt',
    is_active: true,
    description: 'Investigate a domain',
    category: 'domain',
    step_count: 0,
    initial_parameters: {},
  }
  const executions = []
  const requestedCases = []
  await page.route('**/api/hunts/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/hunts/') return route.fulfill({ json: [hunt] })
    if (route.request().method() === 'POST') {
      const data = route.request().postDataJSON()
      const execution = {
        id: 8,
        ...data,
        initial_parameters: data.parameters,
        hunt,
        hunt_display_name: hunt.display_name,
        status: 'completed',
        progress: 1,
        created_at: '2026-09-04T00:00:00Z',
        steps: [],
      }
      executions.push(execution)
      return route.fulfill({ json: execution })
    }
    if (path.includes('/cases/')) {
      const id = Number(path.split('/')[4])
      requestedCases.push(id)
      return route.fulfill({ json: executions.filter((execution) => execution.case_id === id) })
    }
    return route.fulfill({ json: executions[0] })
  })
  await page.goto('/hunts')
  await expect(page).toHaveURL(/\/case\/2\/hunts$/)
  await page.getByRole('button', { name: 'Execute Hunt', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Execute Hunt', exact: true })
  await expect(dialog.getByRole('combobox')).toHaveCount(0)
  await dialog.getByRole('button', { name: 'Execute Hunt', exact: true }).click()
  await expect(dialog).toBeHidden()
  expect(executions).toEqual([expect.objectContaining({ case_id: 2, parameters: {} })])
  await page.getByRole('tab', { name: 'Execution History', exact: true }).click()
  await expect(page.getByRole('cell', { name: 'Context Hunt', exact: true })).toBeVisible()
  const switcher = page.getByRole('combobox', { name: 'Active case', exact: true })
  await switcher.fill('CASE-OLD')
  await page
    .getByRole('option', { name: 'CASE-OLD — Older investigation (Closed)', exact: true })
    .click()
  await expect(page).toHaveURL(/\/case\/1\/hunts$/)
  await page.getByRole('tab', { name: 'Execution History', exact: true }).click()
  await expect(page.getByText('No executions found', { exact: true })).toBeVisible()
  expect(requestedCases).toContain(1)
  expect(requestedCases).toContain(2)
  await page.goto('/hunts/execution/8')
  await expect(page).toHaveURL(/\/case\/2\/hunts\/execution\/8$/)
  await expect(switcher).toHaveValue('CASE-NEW — Newer investigation (Open)')
  await page.reload()
  await expect(switcher).toHaveValue('CASE-NEW — Newer investigation (Open)')
  await page.getByRole('button', { name: 'Back to Hunts', exact: true }).click()
  await expect(page).toHaveURL(/\/case\/2\/hunts$/)
  await page.getByRole('tab', { name: 'Execution History', exact: true }).click()
  await expect(page.getByRole('cell', { name: 'Context Hunt', exact: true })).toBeVisible()
})

test('plugins use active context for transient runs, optional saving, and correlation', async ({
  page,
}) => {
  await setup(page)
  const requests = []
  await page.route('**/api/plugins/**', async (route) => {
    if (route.request().method() === 'POST') {
      requests.push(route.request().postDataJSON())
      return route.fulfill({
        body: '{"type":"complete","data":{}}\n',
        contentType: 'application/json',
      })
    }
    return route.fulfill({
      json: {
        ExamplePlugin: {
          name: 'ExamplePlugin',
          display_name: 'Example',
          enabled: true,
          parameters: {
            case_id: { type: 'integer', default: 999 },
            save_to_case: { type: 'boolean', default: false },
          },
        },
        CorrelationScan: {
          name: 'CorrelationScan',
          display_name: 'Correlation Scan',
          enabled: true,
          parameters: {
            case_id: { type: 'integer', required: true },
            save_to_case: { type: 'boolean', default: false },
          },
        },
      },
    })
  })
  await page.goto('/plugins')
  await expect(page).toHaveURL(/\/case\/2\/plugins$/)
  await expect(page.getByRole('link', { name: 'Plugins', exact: true })).toHaveAttribute(
    'href',
    '/case/2/plugins',
  )
  await page.getByRole('button', { name: 'Configure Example', exact: true }).click()
  await expect(page.locator('form').getByRole('combobox')).toHaveCount(0)
  await page.getByRole('button', { name: 'Execute Plugin', exact: true }).click()
  await page.getByRole('button', { name: 'Close plugin results', exact: true }).click()
  expect(requests).toEqual([{ case_id: 2, save_to_case: false }])
  await page.getByLabel('Save to case evidence', { exact: true }).check()
  await page.getByRole('button', { name: 'Execute Plugin', exact: true }).click()
  await page.getByRole('button', { name: 'Close plugin results', exact: true }).click()
  expect(requests[1]).toEqual({ case_id: 2, save_to_case: true })
  const switcher = page.getByRole('combobox', { name: 'Active case', exact: true })
  await switcher.fill('CASE-OLD')
  await page
    .getByRole('option', { name: 'CASE-OLD — Older investigation (Closed)', exact: true })
    .click()
  await expect(page).toHaveURL(/\/case\/1\/plugins$/)
  await expect(page.getByRole('button', { name: 'View Results', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Configure Correlation Scan', exact: true }).click()
  await expect(page.locator('form').getByRole('combobox')).toHaveCount(0)
  await page.getByRole('button', { name: 'Execute Plugin', exact: true }).click()
  await page.getByRole('button', { name: 'Close plugin results', exact: true }).click()
  expect(requests[2]).toEqual({ case_id: 1, save_to_case: false })
  await page.reload()
  await expect(switcher).toHaveValue('CASE-OLD — Older investigation (Closed)')
})

for (const [width, role, keyStatus] of [
  [1440, 'Admin', 200],
  [390, 'Investigator', 403],
]) {
  test(`complete case workspace journey at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await setup(page, role)
    const chatRequests = []
    const pluginRequests = []
    await page.route('**/api/admin/configuration/api-keys/openai/status', (route) =>
      route.fulfill({ status: keyStatus, json: { is_configured: true } }),
    )
    await page.route('**/api/strixy/chat', (route) => {
      const payload = route.request().postDataJSON()
      chatRequests.push(payload)
      return route.fulfill({ json: { message: `Reply for case ${payload.case_id}` } })
    })
    await page.route('**/api/plugins/**', (route) => {
      if (route.request().method() === 'POST') {
        pluginRequests.push(route.request().postDataJSON())
        return route.fulfill({
          body: '{"type":"complete","data":{}}\n',
          contentType: 'application/json',
        })
      }
      return route.fulfill({
        json: {
          ExamplePlugin: {
            name: 'ExamplePlugin',
            display_name: 'Example',
            enabled: true,
            parameters: { save_to_case: { type: 'boolean', default: false } },
          },
        },
      })
    })
    await page.goto('/cases')
    const switcher = page.getByRole('combobox', { name: 'Active case', exact: true })
    await expect(switcher).toHaveValue('CASE-NEW — Newer investigation (Open)')
    const navigate = async (name, suffix) => {
      const link = page.getByRole('link', { name, exact: true })
      await expect(link).toHaveAttribute('href', `/case/2${suffix}`)
      await link.click()
      await expect(page).toHaveURL(new RegExp(`/case/2${suffix}$`))
      await expect(switcher).toBeVisible()
    }
    await navigate('Case overview', '')
    await navigate('Tasks', '/tasks')
    await navigate('Plugins', '/plugins')
    await page.getByRole('button', { name: 'Configure Example', exact: true }).click()
    await expect(page.locator('form').getByRole('combobox')).toHaveCount(0)
    await page.getByRole('button', { name: 'Execute Plugin', exact: true }).click()
    await page.getByRole('button', { name: 'Close plugin results', exact: true }).click()
    expect(pluginRequests).toEqual([{ case_id: 2, save_to_case: false }])
    await navigate('Hunts', '/hunts')
    await navigate('Strixy (WIP)', '/strixy')
    const input = page.getByRole('textbox', { name: 'Message input', exact: true })
    await input.fill('Private question for the newer investigation')
    await input.press('Enter')
    await expect(page.getByText('Reply for case 2', { exact: true })).toBeVisible()
    expect(chatRequests[0]).toMatchObject({ case_id: 2 })
    await input.fill('Unsent private draft')
    await switcher.focus()
    await expect(switcher).toBeFocused()
    await switcher.fill('CASE-OLD')
    await expect(page.getByRole('option', { name: /CASE-OLD/ })).toBeVisible()
    await switcher.press('ArrowDown')
    await switcher.press('Enter')
    await expect(page).toHaveURL(/\/case\/1\/strixy$/)
    await expect(
      page.getByRole('status').filter({ hasText: 'Active case: CASE-OLD' }),
    ).toBeVisible()
    await expect(page.getByText('Strixy · CASE-OLD', { exact: true })).toBeVisible()
    await expect(page.getByText('Reply for case 2', { exact: true })).toHaveCount(0)
    await expect(input).toHaveValue('')
    await input.fill('Question for the older investigation')
    await input.press('Enter')
    await expect(page.getByText('Reply for case 1', { exact: true })).toBeVisible()
    expect(chatRequests[1]).toMatchObject({ case_id: 1 })
    expect(JSON.stringify(chatRequests[1])).not.toContain('Private question')
    for (const [name, suffix] of [
      ['Case overview', ''],
      ['Tasks', '/tasks'],
      ['Plugins', '/plugins'],
      ['Hunts', '/hunts'],
      ['Strixy (WIP)', '/strixy'],
    ]) {
      await expect(page.getByRole('link', { name, exact: true })).toHaveAttribute(
        'href',
        `/case/1${suffix}`,
      )
    }
    await page.getByRole('link', { name: 'Cases', exact: true }).click()
    await page.reload()
    await expect(switcher).toHaveValue('CASE-OLD — Older investigation (Closed)')
    await page.goto('/strixy')
    await expect(page).toHaveURL(/\/case\/1\/strixy$/)
    await expect(switcher).toBeVisible()
  })
}
