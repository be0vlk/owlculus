import { expect, test } from '@playwright/test'
import {
  administrator,
  adminHeaders,
  bootstrap,
  investigatorCases,
  json,
  loginUi,
} from './support/workflow'
import { ready, release } from './execution-support/journey'

test.setTimeout(120_000)
test.beforeAll(async ({ request }) => bootstrap(request))

test('two readers share a fixed snapshot and keep an independent follow-up after revocation and deletion', async ({
  page,
  browser,
  request,
}) => {
  const fixture = await investigatorCases(request)
  const admin = await adminHeaders(request)
  const caseId = fixture.cases[0].id
  const users = await json(await request.get('/api/users/', { headers: admin }))
  const strixy = users.find((user) => user.system_identity === 'strixy')
  await json(await request.post(`/api/cases/${caseId}/users/${strixy.id}`, { headers: admin }))
  await json(
    await request.put('/api/admin/configuration/api-keys/openai', {
      headers: admin,
      data: { api_key: 'deterministic-test-only', name: 'Browser fake' },
    }),
  )
  const base = `/api/strixy/cases/${caseId}/conversations`
  const created = await json(await request.post(base, { headers: fixture.headers }))
  const detail = `${base}/${created.id}`
  const accepted = await request.post(`${detail}/messages`, {
    headers: fixture.headers,
    data: { content: fixture.marker },
  })
  const observation = accepted.headers().location
  const viewerContext = await browser.newContext({ baseURL: test.info().project.use.baseURL })
  const viewer = await viewerContext.newPage()
  try {
    await ready(fixture.marker)
    await release(fixture.marker)
    await expect
      .poll(
        async () =>
          (await json(await request.get(observation, { headers: fixture.headers }))).status,
      )
      .toBe('completed')
    await loginUi(page, fixture.credentials)
    await page.goto(`/case/${caseId}/strixy`)
    const sharedResponse = page.waitForResponse(
      (r) => r.request().method() === 'POST' && r.url().endsWith('/shares'),
    )
    await page.getByRole('button', { name: 'Share conversation', exact: true }).click()
    await page.getByRole('button', { name: 'Create snapshot', exact: true }).click()
    const share = await json(await sharedResponse)
    await expect(page.getByRole('textbox', { name: 'Snapshot link' })).toHaveValue(
      new RegExp(share.id),
    )
    const sharePath = `/case/${caseId}/strixy?share=${share.id}`
    await loginUi(viewer, administrator)
    await viewer.goto(sharePath)
    await expect(viewer.getByText('Read-only snapshot', { exact: false }).first()).toBeVisible()
    await viewer.getByRole('button', { name: /Review details/ }).click()
    await viewer.getByRole('dialog').locator('.v-list-item').first().click()
    await expect(viewer.getByRole('dialog')).toContainText(fixture.cases[0].case_number)
    await viewer.getByRole('button', { name: 'Close source' }).click()
    await json(
      await request.post(`${detail}/messages`, {
        headers: fixture.headers,
        data: { content: 'Later private question' },
      }),
    )
    await viewer.reload()
    await expect(
      viewer.getByText(`Saved Strixy reply ${fixture.marker}`, { exact: true }),
    ).toBeVisible()
    await expect(viewer.getByText('Later private question', { exact: true })).toHaveCount(0)
    const copiedResponse = viewer.waitForResponse((r) => r.url().endsWith('/copy'))
    await viewer.getByRole('button', { name: 'Start private follow-up', exact: true }).click()
    const copied = await json(await copiedResponse)
    await expect(viewer.getByRole('textbox', { name: 'Message input' })).toBeEnabled()
    await page.getByRole('button', { name: 'Revoke snapshot', exact: true }).click()
    await expect(page.getByRole('textbox', { name: 'Snapshot link' })).toHaveCount(0)
    await viewer.goto(sharePath)
    await expect(viewer.getByText('Snapshot unavailable.', { exact: false })).toBeVisible()
    await page.getByRole('button', { name: 'Close sharing', exact: true }).click()
    await page.getByRole('button', { name: 'Conversation actions', exact: true }).click()
    await page.getByText('Delete conversation', { exact: true }).click()
    await page.getByRole('button', { name: 'Delete', exact: true }).click()
    await expect
      .poll(async () => (await request.get(detail, { headers: fixture.headers })).status())
      .toBe(404)
    expect((await request.get(`${base}/${copied.id}`, { headers: admin })).status()).toBe(200)
    await viewer.goto(`/case/${caseId}/strixy`)
    await expect(
      viewer.getByText(`Saved Strixy reply ${fixture.marker}`, { exact: true }),
    ).toBeVisible()
    await expect(viewer.getByText('Later private question', { exact: true })).toHaveCount(0)
  } finally {
    await release(fixture.marker)
    await viewerContext.close()
  }
})
