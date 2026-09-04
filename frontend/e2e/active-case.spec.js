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

// Disposable browser context and authorized API fixtures keep this shell journey
// independent of the later tool migrations and of any developer database.
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
