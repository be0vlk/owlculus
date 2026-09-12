import { expect, test } from '@playwright/test'
import { adminHeaders, bootstrap, investigatorCases, json, loginUi } from './support/workflow'
import { ready, release, starts } from './execution-support/journey'

test.use({ trace: 'retain-on-failure', screenshot: 'only-on-failure' })
test.setTimeout(120_000)
test.beforeAll(async ({ request }) => bootstrap(request))

test('private Strixy conversations survive navigation and keep delayed replies in their Case', async ({
  page,
  request,
}) => {
  const fixture = await investigatorCases(request)
  const admin = await adminHeaders(request)
  const users = await json(await request.get('/api/users/', { headers: admin }))
  const strixy = users.find((user) => user.system_identity === 'strixy')
  expect(strixy).toBeTruthy()
  for (const item of fixture.cases) {
    await json(await request.post(`/api/cases/${item.id}/users/${strixy.id}`, { headers: admin }))
  }
  await json(
    await request.put('/api/admin/configuration/api-keys/openai', {
      headers: admin,
      data: { api_key: 'deterministic-test-only', name: 'Browser fake' },
    }),
  )
  const original = `/case/${fixture.cases[0].id}/strixy`
  try {
    await loginUi(page, fixture.credentials)
    await page.goto(original)
    await page.getByRole('textbox', { name: 'Message input' }).fill(fixture.marker)
    const acceptance = page.waitForResponse(
      (response) => response.request().method() === 'POST' && response.url().endsWith('/messages'),
    )
    await page.getByRole('button', { name: 'Send message' }).click()
    const accepted = await acceptance
    expect(accepted.status()).toBe(202)
    const run = await accepted.json()
    await ready(fixture.marker)
    await page.goto(`/case/${fixture.cases[1].id}/strixy`)
    await expect(page.getByText(fixture.marker, { exact: true })).toHaveCount(0)
    await release(fixture.marker)
    const observation = accepted.headers().location
    await expect
      .poll(
        async () =>
          (await json(await request.get(observation, { headers: fixture.headers }))).status,
      )
      .toBe('completed')
    await expect(
      page.getByText(`Saved Strixy reply ${fixture.marker}`, { exact: true }),
    ).toHaveCount(0)
    await page.goto(original)
    await expect(
      page.getByText(`Saved Strixy reply ${fixture.marker}`, { exact: true }),
    ).toBeVisible()
    await page.reload()
    await expect(
      page.getByText(`Saved Strixy reply ${fixture.marker}`, { exact: true }),
    ).toHaveCount(1)
    await page.getByRole('button', { name: 'Start new conversation' }).click()
    await expect(
      page.getByText(`Saved Strixy reply ${fixture.marker}`, { exact: true }),
    ).toHaveCount(0)
    await page.getByRole('combobox', { name: 'Private conversations' }).press('Enter')
    await page.getByRole('option', { name: /Conversation 1/ }).click()
    await expect(
      page.getByText(`Saved Strixy reply ${fixture.marker}`, { exact: true }),
    ).toBeVisible()
    expect((await json(await request.get(observation, { headers: fixture.headers }))).id).toBe(
      run.id,
    )
    expect(await starts(fixture.marker)).toBe(1)
  } finally {
    await release(fixture.marker)
  }
})
