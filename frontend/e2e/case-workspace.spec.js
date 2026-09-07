import process from 'node:process'
import { expect, test } from '@playwright/test'

async function setup(
  page,
  { theme = 'light', long = false, state = 'populated', role = 'Admin' } = {},
) {
  const record = {
    id: 1,
    case_number: 'CASE-2026-041',
    title: long
      ? 'Investigation of international infrastructure and associated organizations — North Atlantic operations with extended source identifiers'
      : 'North Atlantic infrastructure',
    status: 'Open',
    created_at: '2026-01-01T00:00:00Z',
    client_id: 1,
    notes: '<p>Saved investigation notes</p>',
    users: Array.from({ length: long ? 24 : 2 }, (_, i) => ({
      id: i + 1,
      username: `investigator-${i + 1}`,
      email: `investigator${i + 1}@example.org`,
      role: 'Investigator',
      is_lead: i === 0,
    })),
  }
  await page.addInitScript(
    ({ theme }) => {
      localStorage.setItem('access_token', 'browser-fixture')
      localStorage.setItem('color-scheme', theme)
    },
    { theme },
  )
  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    let body = []
    if (path === '/api/auth/setup-status') body = { setup_required: false }
    else if (path === '/api/users/me') body = { id: 1, role, username: 'investigator' }
    else if (path === '/api/cases/') body = [record]
    else if (path === '/api/cases/1') {
      if (request.method() === 'PUT') Object.assign(record, request.postDataJSON())
      body = record
    } else if (path === '/api/clients/1') body = { id: 1, name: 'North Atlantic Research' }
    else if (path === '/api/users/')
      body = [{ id: 50, username: 'new-member', email: 'new@example.org', role: 'Investigator' }]
    else if (path === '/api/cases/1/users/50') {
      record.users.push({
        id: 50,
        username: 'new-member',
        email: 'new@example.org',
        role: 'Investigator',
      })
      body = record
    } else if (path === '/api/cases/1/export')
      return route.fulfill({ contentType: 'application/zip', body: 'fixture bundle' })
    else if (path.endsWith('/entities')) {
      if (state === 'error')
        return route.fulfill({ status: 503, json: { detail: 'Entities temporarily unavailable' } })
      if (state === 'loading') await new Promise((resolve) => setTimeout(resolve, 2500))
      body =
        state === 'empty'
          ? []
          : [
              {
                id: 11,
                entity_type: 'domain',
                data: {
                  domain: long
                    ? 'research-infrastructure-with-an-extended-source-identifier.example.org'
                    : 'infrastructure.example.org',
                },
                created_at: record.created_at,
              },
            ]
    } else if (path.includes('/folder-tree'))
      body =
        state === 'empty'
          ? []
          : [
              {
                id: 20,
                title: long
                  ? 'Infrastructure source evidence and extended archived collection identifiers'
                  : 'Source evidence',
                is_folder: true,
                children: [],
                case_id: 1,
              },
            ]
    else if (path.includes('/plugins/executions/case/')) body = { items: [], next_cursor: null }
    await route.fulfill({ json: body })
  })
  return record
}

const details = (page) => page.getByRole('dialog', { name: 'Case details', exact: true })
const detailsButton = (page) => page.getByRole('button', { name: 'Case details', exact: true })

async function addMember(page, users) {
  await users.getByLabel('Select User', { exact: true }).press('ArrowDown')
  await page.getByRole('option', { name: /new@example.org/ }).click()
  await users.getByRole('button', { name: 'Add User', exact: true }).click()
  await expect(
    users.getByRole('button', { name: 'Remove new@example.org from case', exact: true }),
  ).toBeVisible()
}

test('details and nested dialogs preserve focus, workspace draft and successful edits', async ({
  page,
}) => {
  await setup(page)
  await page.goto('/case/1?tab=notes')
  await expect(details(page)).toBeHidden()
  await page.getByRole('button', { name: 'Edit Notes', exact: true }).click()
  const editor = page.getByRole('textbox', { name: 'Case notes', exact: true })
  await editor.fill('Unsaved investigative draft')
  await detailsButton(page).focus()
  await detailsButton(page).press('Enter')
  await expect(details(page)).toContainText('North Atlantic Research')
  await expect(details(page)).toContainText('Lead')
  const edit = details(page).getByRole('button', { name: 'Edit Case', exact: true })
  await edit.click()
  const modal = page.getByRole('dialog', { name: 'Edit Case', exact: true })
  await modal
    .getByRole('textbox', { name: 'Case Title', exact: true })
    .fill('Updated investigation')
  await modal.getByRole('button', { name: 'Save Changes', exact: true }).click()
  await expect(modal).toBeHidden()
  await expect(edit).toBeFocused()
  await expect(details(page)).toContainText('Updated investigation')
  await edit.press('Enter')
  await modal.getByRole('textbox', { name: 'Case Title', exact: true }).press('Escape')
  await expect(edit).toBeFocused()
  await expect(details(page)).toBeVisible()
  const manage = details(page).getByRole('button', { name: 'Manage Users', exact: true })
  await manage.click()
  const users = page.getByRole('dialog', { name: 'Manage Case Users', exact: true })
  await addMember(page, users)
  await users.getByRole('button', { name: 'Done', exact: true }).click()
  await expect(manage).toBeFocused()
  await expect(details(page)).toContainText('new-member')
  await manage.press('Escape')
  await expect(details(page)).toBeHidden()
  await expect(detailsButton(page)).toBeFocused()
  await expect(page.getByRole('heading', { name: /Updated investigation/ })).toBeVisible()
  await expect(editor).toContainText('Unsaved investigative draft')
  await page.getByRole('tab', { name: 'Entities', exact: true }).click()
  await page.getByRole('tab', { name: 'Notes', exact: true }).click()
  await expect(editor).toContainText('Unsaved investigative draft')
  await detailsButton(page).click()
  await details(page).getByRole('button', { name: 'Close Case details', exact: true }).click()
  await expect(detailsButton(page)).toBeFocused()
  const download = page.waitForEvent('download')
  await page.getByTestId('case-export-button').click()
  expect((await download).suggestedFilename()).toContain('CASE-2026-041')
})

if (process.env.OWLCULUS_WORKSPACE_EVIDENCE) {
  for (const [width, height] of [
    [1440, 900],
    [1366, 768],
    [3440, 1440],
    [390, 844],
  ]) {
    for (const theme of ['light', 'dark']) {
      test(`render workspace ${width} ${theme}`, async ({ page }) => {
        await page.setViewportSize({ width, height })
        await setup(page, { theme, long: true })
        await page.goto('/case/1')
        await expect(page.getByRole('link', { name: 'Cases', exact: true })).toBeVisible()
        await expect(page.getByRole('cell', { name: /^research-infrastructure/ })).toBeVisible()
        const phase = process.env.OWLCULUS_WORKSPACE_EVIDENCE
        const capture = (name) =>
          page.screenshot({
            animations: 'disabled',
            path: `../.scratch/case-workspace-polish/evidence/workspace/${phase}-${width}-${theme}-${name}.png`,
          })
        await capture('entities')
        if (phase === 'after') {
          expect(
            await page.evaluate(
              () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
            ),
          ).toBe(true)
          await expect(
            page.getByRole('button', { name: 'Add Entity', exact: true }),
          ).toBeInViewport()
          await detailsButton(page).click()
          await expect(details(page)).toContainText('investigator-24')
          await capture('details')
          await details(page)
            .getByRole('button', { name: 'Close Case details', exact: true })
            .click()
        }
        await page.getByRole('tab', { name: 'Evidence', exact: true }).click()
        await expect(
          page.getByRole('button', { name: 'Upload Evidence', exact: true }),
        ).toBeVisible()
        await capture('evidence')
        await page.getByRole('tab', { name: 'Notes', exact: true }).click()
        await expect(page.getByText('Saved investigation notes', { exact: true })).toBeVisible()
        await capture('notes')
      })
    }
  }
}

for (const role of ['Analyst', 'Investigator']) {
  test(`${role} details preserve authorization and missing metadata states`, async ({ page }) => {
    const record = await setup(page, { role })
    record.users = []
    record.client_id = null
    record.created_at = null
    await page.goto('/case/1')
    await detailsButton(page).click()
    await expect(details(page)).toContainText('No client assigned')
    await expect(details(page)).toContainText('No users assigned')
    await expect(details(page)).toContainText('N/A')
    await expect(
      details(page).getByRole('button', { name: 'Manage Users', exact: true }),
    ).toHaveCount(0)
    await expect(details(page).getByRole('button', { name: 'Edit Case', exact: true })).toHaveCount(
      role === 'Analyst' ? 0 : 1,
    )
  })
}

if (process.env.OWLCULUS_WORKSPACE_EVIDENCE === 'after') {
  for (const [width, height] of [
    [1440, 900],
    [1366, 768],
    [3440, 1440],
    [390, 844],
  ]) {
    for (const theme of ['light', 'dark']) {
      test(`workspace feedback ${width} ${theme}`, async ({ page }) => {
        await page.setViewportSize({ width, height })
        await page.emulateMedia({ reducedMotion: 'reduce' })
        await setup(page, { theme, state: 'empty' })
        let release
        const gate = new Promise((resolve) => {
          release = resolve
        })
        let fail = false
        await page.route('**/api/cases/1/entities?*', async (route) => {
          await gate
          await route.fulfill(
            fail
              ? { status: 503, json: { detail: 'Entities temporarily unavailable' } }
              : { json: [] },
          )
        })
        const capture = (state) =>
          page.screenshot({
            animations: 'disabled',
            path: `../.scratch/case-workspace-polish/evidence/workspace/after-${width}-${theme}-${state}.png`,
          })
        await page.goto('/case/1')
        await expect(page.getByRole('progressbar').first()).toBeVisible()
        await capture('loading')
        release()
        await expect(page.getByText('No Entities Found', { exact: true })).toBeVisible()
        await capture('empty')
        fail = true
        await page.reload()
        await expect(page.getByTestId('entity-load-error')).toContainText(
          'Entities temporarily unavailable',
        )
        await capture('error')
        fail = false
        await page.getByRole('button', { name: 'Retry', exact: true }).click()
        await expect(page.getByText('No Entities Found', { exact: true })).toBeVisible()
        const entities = page.getByRole('tab', { name: 'Entities', exact: true })
        await entities.focus()
        await entities.press('ArrowRight')
        const evidence = page.getByRole('tab', { name: 'Evidence', exact: true })
        await expect(evidence).toBeFocused()
        await evidence.press('Enter')
        await expect(evidence).toHaveAttribute('aria-selected', 'true')
        await expect(
          page.getByRole('button', { name: 'Upload Evidence', exact: true }),
        ).toBeDisabled()
        await capture('evidence-empty')
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
          ),
        ).toBe(true)
      })
    }
  }
}

test('failed membership refresh keeps the draft and can be retried in details', async ({
  page,
}) => {
  const record = await setup(page)
  await page.goto('/case/1?tab=notes')
  await page.getByRole('button', { name: 'Edit Notes', exact: true }).click()
  const editor = page.getByRole('textbox', { name: 'Case notes', exact: true })
  await editor.fill('Draft during membership refresh')
  await detailsButton(page).click()
  await details(page).getByRole('button', { name: 'Manage Users', exact: true }).click()
  const users = page.getByRole('dialog', { name: 'Manage Case Users', exact: true })
  await page.route('**/api/cases/1', (route) =>
    route.fulfill({ status: 503, json: { detail: 'Temporarily unavailable' } }),
  )
  await users.getByLabel('Select User', { exact: true }).press('ArrowDown')
  await page.getByRole('option', { name: /new@example.org/ }).click()
  await users.getByRole('button', { name: 'Add User', exact: true }).click()
  await users.getByRole('button', { name: 'Done', exact: true }).click()
  await expect(details(page)).toContainText('Failed to refresh case details')
  await page.route('**/api/cases/1', (route) => route.fulfill({ json: record }))
  await details(page).getByRole('button', { name: 'Retry case details', exact: true }).click()
  await expect(details(page)).toContainText('new-member')
  await expect(details(page)).not.toContainText('Failed to refresh case details')
  await details(page).getByRole('button', { name: 'Close Case details', exact: true }).click()
  await expect(editor).toContainText('Draft during membership refresh')
})
