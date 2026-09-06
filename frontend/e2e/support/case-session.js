import { randomUUID } from 'node:crypto'
import { expect, test as base } from '@playwright/test'
import { adminHeaders, createCase, json } from './workflow'

// Delays retain the real backend response and always release on test failure.
export const test = base.extend({
  holdResponse: async ({ page }, use) => {
    const holds = []
    await use(async (matches) => {
      let release
      let accepted
      let failed
      let finished
      const gate = new Promise((resolve) => {
        release = resolve
      })
      const ready = new Promise((resolve, reject) => {
        accepted = resolve
        failed = reject
      })
      // A transport failure can arrive before the caller starts awaiting readiness.
      ready.catch(() => {})
      const done = new Promise((resolve) => {
        finished = resolve
      })
      let captured = false
      const handler = async (route) => {
        if (captured || !matches(route.request())) return route.fallback()
        captured = true
        try {
          const response = await route.fetch({ timeout: 10_000 })
          accepted(await json(response))
          await gate
          const delivered = page.waitForEvent('requestfinished', {
            predicate: (request) => request === route.request(),
            timeout: 10_000,
          })
          await route.fulfill({ response })
          await delivered
        } catch (error) {
          failed(error)
          throw error
        } finally {
          finished()
        }
      }
      await page.route('**/api/**', handler)
      const hold = { ready, release, done }
      holds.push(hold)
      return hold
    })
    for (const hold of holds) hold.release()
    await page.unrouteAll({ behavior: 'wait' })
  },
})

export async function createUser(request, role = 'Investigator') {
  const admin = await adminHeaders(request)
  const marker = randomUUID()
  const credentials = {
    username: `session_${marker.slice(0, 8)}`,
    email: `${marker}@example.org`,
    password: 'SessionPassword123!',
  }
  const user = await json(
    await request.post('/api/users/', {
      headers: admin,
      data: { ...credentials, role, is_active: true },
    }),
  )
  const session = await json(await request.post('/api/auth/login', { form: credentials }))
  return { user, credentials, headers: { Authorization: `bearer ${session.access_token}` } }
}

export async function caseWorkspace(request, role = 'Investigator') {
  const account = await createUser(request, role)
  const admin = await adminHeaders(request)
  const cases = []
  for (const label of ['Original', 'Other']) {
    const title = `${label} ${randomUUID()}`
    const record = await createCase(request, admin, title)
    await json(
      await request.post(`/api/cases/${record.id}/users/${account.user.id}`, {
        headers: admin,
        data: { is_lead: role === 'Investigator' },
      }),
    )
    const notes = `${title} private notes`
    await json(
      await request.put(`/api/cases/${record.id}`, {
        headers: admin,
        data: { notes: `<p>${notes}</p>` },
      }),
    )
    const task = await json(
      await request.post('/api/tasks/', {
        headers: admin,
        data: {
          case_id: record.id,
          title: `${title} task`,
          description: `${title} findings`,
          assigned_to_id: account.user.id,
        },
      }),
    )
    cases.push({ ...record, notes, task })
  }
  return { ...account, admin, cases }
}

export async function switchCase(page, record) {
  const switcher = page.getByRole('combobox', { name: /^Active case:/ })
  await switcher.press('ArrowDown')
  await page
    .getByRole('option', {
      name: new RegExp(`^${record.case_number}\\b`),
    })
    .click()
  await expect(switcher).toHaveValue(`${record.case_number} — ${record.title} (${record.status})`)
}

export async function notesVisible(page, selected, excluded) {
  await expect(page.getByText(selected.notes, { exact: true })).toBeVisible()
  await expect(page.getByText(excluded.notes, { exact: true })).toHaveCount(0)
}

export async function tasksVisible(page, selected, excluded) {
  await expect(page.getByRole('link', { name: selected.task.title, exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: excluded.task.title, exact: true })).toHaveCount(0)
}

export async function persistedWorkspace(request, headers, record) {
  expect(await json(await request.get(`/api/cases/${record.id}`, { headers }))).toMatchObject({
    id: record.id,
    notes: `<p>${record.notes}</p>`,
  })
  expect(await json(await request.get(`/api/tasks/${record.task.id}`, { headers }))).toMatchObject({
    id: record.task.id,
    case_id: record.id,
    title: record.task.title,
  })
}

export function caseRead(record) {
  return (request) =>
    request.method() === 'GET' && new URL(request.url()).pathname === `/api/cases/${record.id}`
}

export function taskList(record) {
  return (request) => {
    const url = new URL(request.url())
    return (
      request.method() === 'GET' &&
      url.pathname === '/api/tasks/' &&
      url.searchParams.get('case_id') === String(record.id)
    )
  }
}
