import process from 'node:process'
import { randomUUID } from 'node:crypto'
import { expect, test } from '@playwright/test'

// Run this file on its own disposable stack through the browser runner. Only
// bootstrap is shared; every test creates its own accounts and investigation data.
const administrator = {
  username: 'coverage_admin',
  email: 'coverage-admin@example.org',
  password: 'CoveragePassword123!',
}

async function json(response) {
  const body = await response.json()
  expect(
    response.ok(),
    `API ${response.url()}: ${response.status()}${response.ok() ? '' : ` ${JSON.stringify(body)}`}`,
  ).toBe(true)
  return body
}

async function loginApi(request, credentials) {
  return json(await request.post('/api/auth/login', { form: credentials }))
}

async function adminHeaders(request) {
  const session = await loginApi(request, {
    username: administrator.username,
    password: administrator.password,
  })
  return { Authorization: `${session.token_type} ${session.access_token}` }
}

async function createCase(request, headers, title) {
  const client = await json(
    await request.post('/api/clients/', {
      headers,
      data: { name: title, email: `client-${randomUUID()}@example.org` },
    }),
  )
  return json(await request.post('/api/cases/', { headers, data: { title, client_id: client.id } }))
}

async function createAnalystCase(request) {
  const headers = await adminHeaders(request)
  const credentials = {
    username: `analyst_${randomUUID().slice(0, 8)}`,
    email: `analyst-${randomUUID()}@example.org`,
    password: 'AnalystPassword123!',
  }
  const analyst = await json(
    await request.post('/api/users/', {
      headers,
      data: { ...credentials, role: 'Analyst', is_active: true },
    }),
  )
  const assignedCase = await createCase(request, headers, `Analyst case ${randomUUID()}`)
  await json(await request.post(`/api/cases/${assignedCase.id}/users/${analyst.id}`, { headers }))
  return { credentials, assignedCase }
}

async function loginUi(page, credentials) {
  await page.goto('/login')
  await page.getByLabel('Username', { exact: true }).fill(credentials.username)
  await page.getByLabel('Password', { exact: true }).fill(credentials.password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page).toHaveURL(/\/cases$/)
}

test.beforeAll(async ({ request }) => {
  expect(process.env.OWLCULUS_SETUP_TOKEN, 'Use the disposable-stack browser runner').toBeTruthy()
  const setup = await json(await request.get('/api/auth/setup-status'))
  if (setup.setup_required) {
    await json(
      await request.post('/api/users/', {
        data: { ...administrator, setup_token: process.env.OWLCULUS_SETUP_TOKEN },
      }),
    )
  }
  // Also supports retrying this file on its own stack after bootstrap succeeded.
  await adminHeaders(request)
})

test('redeems an invite using keyboard controls, then logs in with the created account', async ({
  page,
  request,
}) => {
  const headers = await adminHeaders(request)
  const invite = await json(
    await request.post('/api/invites/', { headers, data: { role: 'Investigator' } }),
  )
  const invited = {
    username: `invited_${randomUUID().slice(0, 8)}`,
    email: `invited-${randomUUID()}@example.org`,
    password: 'InvitedPassword123!',
  }
  const writes = []
  page.on('request', (request) => {
    if (
      request.method() === 'POST' &&
      new URL(request.url()).pathname === '/api/invites/register'
    ) {
      writes.push(request.postDataJSON())
    }
  })
  await page.goto(`/register?token=${encodeURIComponent(invite.token)}`)
  await expect(
    page.getByText("You're registering as a Investigator", { exact: true }),
  ).toBeVisible()
  await page.getByLabel('Username', { exact: true }).fill('ab')
  await page.getByLabel('Email Address', { exact: true }).fill(invited.email)
  await page.getByLabel('Password', { exact: true }).fill(invited.password)
  const confirmation = page.getByLabel('Confirm Password', { exact: true })
  await confirmation.fill(invited.password)
  const submit = page.getByRole('button', { name: 'Create Account', exact: true })
  await expect(submit).toBeDisabled()
  await confirmation.press('Enter')
  await expect(submit).toBeDisabled()
  expect(writes).toEqual([])

  await page.getByLabel('Username', { exact: true }).fill(invited.username)
  await confirmation.fill('different-password')
  await expect(submit).toBeDisabled()
  await confirmation.press('Enter')
  await expect(submit).toBeDisabled()
  expect(writes).toEqual([])

  await confirmation.fill(invited.password)
  await expect(submit).toBeEnabled()
  const registered = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/api/invites/register',
  )
  await confirmation.press('Enter')
  const created = await json(await registered)
  expect(created).toMatchObject({
    username: invited.username,
    email: invited.email,
    role: 'Investigator',
  })
  expect(writes).toEqual([{ ...invited, token: invite.token }])
  await expect(
    page.getByRole('alert').filter({ hasText: 'Registration Successful!' }),
  ).toBeVisible()
  expect(await page.evaluate(() => localStorage.getItem('access_token'))).toBeNull()
  await expect(page).toHaveURL(/\/login$/)
  await loginUi(page, invited)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const currentUser = await json(
    await request.get('/api/users/me', { headers: { Authorization: `bearer ${token}` } }),
  )
  expect(currentUser).toMatchObject({
    id: created.id,
    username: invited.username,
    role: 'Investigator',
  })
  const usedInvite = await json(
    await request.post('/api/invites/validate', { data: { token: invite.token } }),
  )
  expect(usedInvite).toMatchObject({ valid: false, error: 'Invite has already been used' })
})

test('denies direct restricted routes to an Analyst with an assigned Case', async ({
  page,
  request,
}) => {
  const { credentials, assignedCase } = await createAnalystCase(request)
  await loginUi(page, credentials)
  // Client-list requests originate from the fallback Cases dashboard; their
  // separate intended no-request regression below remains an expected failure.
  const prohibitedRequests = []
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname
    if (path.startsWith('/api/admin/') || path.startsWith('/api/hunts/')) {
      prohibitedRequests.push(path)
    }
  })
  for (const path of [
    '/admin',
    '/clients',
    '/hunts',
    '/hunts/execution/999999',
    `/case/${assignedCase.id}/hunts`,
    `/case/${assignedCase.id}/hunts/execution/999999`,
  ]) {
    await page.goto(path)
    await expect(page).toHaveURL(/\/cases$/)
    await expect(page.getByRole('button', { name: 'Generate Invite', exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Execute Hunt', exact: true })).toHaveCount(0)
  }
  expect(prohibitedRequests).toEqual([])
  await page.goto(`/case/${assignedCase.id}`)
  await expect(
    page.getByRole('heading', { name: `Case: ${assignedCase.case_number}`, exact: true }),
  ).toBeVisible()
})

test('does not request the denied client list from an Analyst dashboard', async ({
  page,
  request,
}) => {
  const { credentials, assignedCase } = await createAnalystCase(request)
  const clientRequests = []
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === '/api/clients/') clientRequests.push(request.method())
  })
  await loginUi(page, credentials)
  await expect(page.getByRole('cell', { name: assignedCase.title, exact: true })).toBeVisible()
  // Mark only after successful fixture setup and visible dashboard completion.
  // .scratch/frontend-test-coverage-defects/issues/05-browser-analyst-clients.md
  test.fail(true, 'Analyst Cases dashboard loads a client list the backend forbids')
  expect(clientRequests).toEqual([])
})

test('persists a Task edit through the detail dialog and reloads the acknowledged record', async ({
  page,
  request,
}) => {
  const headers = await adminHeaders(request)
  const assignedCase = await createCase(request, headers, `Task case ${randomUUID()}`)
  const task = await json(
    await request.post('/api/tasks/', {
      headers,
      data: {
        case_id: assignedCase.id,
        title: 'Review original evidence',
        description: 'Original description',
      },
    }),
  )
  await loginUi(page, administrator)
  await page.goto(`/case/${assignedCase.id}/tasks/${task.id}`)
  await expect(
    page.getByRole('heading', { name: `Task: ${task.title}`, exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Edit Task', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Edit Task', exact: true })
  const title = 'Review acknowledged evidence'
  const description = 'Saved from the real browser detail workflow'
  await dialog.getByLabel('Title', { exact: true }).fill(title)
  await dialog.getByLabel('Description', { exact: true }).fill(description)
  const updated = page.waitForResponse(
    (response) =>
      response.request().method() === 'PUT' &&
      new URL(response.url()).pathname === `/api/tasks/${task.id}`,
  )
  await dialog.getByLabel('Title', { exact: true }).press('Enter')
  const savedResponse = await updated
  expect(savedResponse.request().postDataJSON()).toMatchObject({
    title,
    description,
    case_id: assignedCase.id,
  })
  expect(await json(savedResponse)).toMatchObject({ id: task.id, title, description })
  await expect(dialog).toBeHidden()
  await expect(page.getByRole('heading', { name: `Task: ${title}`, exact: true })).toBeVisible()
  expect(await json(await request.get(`/api/tasks/${task.id}`, { headers }))).toMatchObject({
    title,
    description,
  })
  await page.reload()
  await expect(page.getByRole('heading', { name: `Task: ${title}`, exact: true })).toBeVisible()
  await expect(page.getByText(description, { exact: true })).toBeVisible()
  await page.goto(`/case/${assignedCase.id}/tasks`)
  await page.getByText('All Tasks', { exact: true }).click()
  await expect(page.getByRole('link', { name: title, exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: task.title, exact: true })).toHaveCount(0)
})
