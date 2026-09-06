import process from 'node:process'
import { randomUUID } from 'node:crypto'
import { expect } from '@playwright/test'

export const administrator = {
  username: 'coverage_admin',
  email: 'coverage-admin@example.org',
  password: 'CoveragePassword123!',
}

export async function json(response) {
  expect(
    response.ok(),
    `API ${response.url()}: ${response.status()} ${await response.text()}`,
  ).toBe(true)
  return response.json()
}

async function loginApi(request, credentials) {
  const session = await json(await request.post('/api/auth/login', { form: credentials }))
  return { Authorization: `${session.token_type} ${session.access_token}` }
}

export async function adminHeaders(request) {
  return loginApi(request, administrator)
}

export async function createCase(request, headers, title) {
  const client = await json(
    await request.post('/api/clients/', {
      headers,
      data: { name: title, email: `client-${randomUUID()}@example.org` },
    }),
  )
  return json(await request.post('/api/cases/', { headers, data: { title, client_id: client.id } }))
}

export async function bootstrap(request) {
  expect(process.env.OWLCULUS_SETUP_TOKEN, 'Use the disposable-stack browser runner').toBeTruthy()
  const setup = await json(await request.get('/api/auth/setup-status'))
  if (setup.setup_required) {
    await json(
      await request.post('/api/users/', {
        data: { ...administrator, setup_token: process.env.OWLCULUS_SETUP_TOKEN },
      }),
    )
  }
  await loginApi(request, administrator)
}

export async function investigatorCases(request) {
  const admin = await loginApi(request, administrator)
  const marker = randomUUID()
  const credentials = {
    username: `exec_${marker.slice(0, 8)}`,
    email: `${marker}@example.org`,
    password: 'InvestigatorPassword123!',
  }
  const user = await json(
    await request.post('/api/users/', {
      headers: admin,
      data: { ...credentials, role: 'Investigator', is_active: true },
    }),
  )
  const cases = []
  for (const name of ['Original', 'Other']) {
    const assignedCase = await createCase(request, admin, `${name} ${marker}`)
    await json(
      await request.post(`/api/cases/${assignedCase.id}/users/${user.id}`, { headers: admin }),
    )
    cases.push(assignedCase)
  }
  return { marker, credentials, cases, headers: await loginApi(request, credentials) }
}

export async function loginUi(page, credentials) {
  await page.goto('/login')
  await page.getByLabel('Username', { exact: true }).fill(credentials.username)
  await page.getByLabel('Password', { exact: true }).fill(credentials.password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page).toHaveURL(/\/cases$/)
}
