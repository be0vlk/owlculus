import { Buffer } from 'node:buffer'
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
  await json(
    await request.post('/api/evidence/folders', {
      headers: admin,
      data: { case_id: fixture.cases[0].id, title: 'Documents' },
    }),
  )
  const uploaded = await json(
    await request.post(
      `/api/evidence/?title=witness&case_id=${fixture.cases[0].id}&category=Documents`,
      {
        headers: admin,
        multipart: {
          files: {
            name: 'witness.txt',
            mimeType: 'text/plain',
            buffer: Buffer.from('Ada works at Acme. Employer disputed.'),
          },
        },
      },
    ),
  )
  expect(uploaded.failed).toEqual([])
  const attachment = uploaded.created[0]
  const unsupported = await json(
    await request.post(
      `/api/evidence/?title=unsupported&case_id=${fixture.cases[0].id}&category=Documents`,
      {
        headers: admin,
        multipart: {
          files: {
            name: 'unexamined.html',
            mimeType: 'text/html',
            buffer: Buffer.from('<p>Unexamined source</p>'),
          },
        },
      },
    ),
  )
  expect(unsupported.failed).toEqual([])
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
    await expect(page.getByText('Case briefing:', { exact: false })).toBeVisible()
    const savedReply = page
      .getByRole('listitem')
      .filter({ hasText: `Saved Strixy reply ${fixture.marker}` })
    await expect(
      savedReply.getByText('This attachment format is not supported for analysis.', {
        exact: false,
      }),
    ).toBeVisible()
    await expect(
      savedReply.getByText(`evidence:${attachment.id}: Attachment examined.`, { exact: false }),
    ).toBeVisible()
    await page
      .getByRole('button', { name: `evidence:${attachment.id} · attachment:line:1`, exact: true })
      .click()
    await expect(page.getByRole('dialog')).toContainText('Ada works at Acme. Employer disputed.')
    await page.getByRole('button', { name: 'Close source' }).click()
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

const beforeRelease = {
  cancel: async (page) => {
    await page.getByRole('button', { name: 'Cancel analysis', exact: true }).click()
    await expect(page.getByText('Analysis cancelled.', { exact: false })).toBeVisible()
  },
}
const recovery = {
  limit: { terminal: 'completed', action: 'Continue analysis' },
  cancel: { terminal: 'cancelled', action: 'Continue analysis' },
  failure: { terminal: 'failed', action: 'Retry analysis' },
}

for (const mode of ['limit', 'cancel', 'failure']) {
  test(`long analysis preserves partial findings and supports explicit ${mode} recovery`, async ({
    page,
    request,
  }) => {
    const fixture = await investigatorCases(request)
    const admin = await adminHeaders(request)
    const users = await json(await request.get('/api/users/', { headers: admin }))
    const strixy = users.find((user) => user.system_identity === 'strixy')
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
      await page.getByRole('textbox', { name: 'Message input' }).fill(`${fixture.marker}|${mode}`)
      const acceptance = page.waitForResponse(
        (response) =>
          response.request().method() === 'POST' && response.url().endsWith('/messages'),
      )
      await page.getByRole('button', { name: 'Send message' }).click()
      const accepted = await acceptance
      expect(accepted.status()).toBe(202)
      await ready(fixture.marker)
      await expect(page.getByText('Preparing findings', { exact: true })).toBeVisible()
      await expect(
        page.getByText(`Partial Strixy reply ${fixture.marker}`, { exact: true }),
      ).toBeVisible()
      await page.goto(`/case/${fixture.cases[1].id}/strixy`)
      await expect(
        page.getByText(`Partial Strixy reply ${fixture.marker}`, { exact: true }),
      ).toHaveCount(0)
      await page.goto(original)
      await page.reload()
      await expect(
        page.getByText(`Partial Strixy reply ${fixture.marker}`, { exact: true }),
      ).toHaveCount(1)
      await page
        .getByRole('button', { name: `case:${fixture.cases[0].id} · case_number`, exact: true })
        .click()
      await expect(page.getByRole('dialog')).toContainText(fixture.cases[0].case_number)
      await page.getByRole('button', { name: 'Close source' }).click()
      await beforeRelease[mode]?.(page)
      await release(fixture.marker)
      await expect
        .poll(
          async () =>
            (
              await json(
                await request.get(accepted.headers().location, { headers: fixture.headers }),
              )
            ).status,
        )
        .toBe(recovery[mode].terminal)
      const action = recovery[mode].action
      await page.getByRole('button', { name: action, exact: true }).click()
      await expect(
        page.getByText(`Saved Strixy reply ${fixture.marker}`, { exact: true }),
      ).toBeVisible()
      await page.reload()
      await expect(
        page.getByText(`Saved Strixy reply ${fixture.marker}`, { exact: true }),
      ).toHaveCount(1)
      await expect(
        page.getByText(`Partial Strixy reply ${fixture.marker}`, { exact: true }),
      ).toHaveCount(1)
      expect(await starts(fixture.marker)).toBe(2)
    } finally {
      await release(fixture.marker)
    }
  })
}
