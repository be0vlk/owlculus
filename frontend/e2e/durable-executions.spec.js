import { expect, test } from '@playwright/test'
import { bootstrap, investigatorCases, json, loginUi } from './support/workflow'
import { executionJourney, ready, release, starts } from './execution-support/journey'

test.describe.configure({ mode: 'default' })
test.use({ actionTimeout: 15_000, trace: 'retain-on-failure', screenshot: 'only-on-failure' })
test.setTimeout(120_000)
test.beforeAll(async ({ request }) => bootstrap(request))

for (const kind of ['plugin', 'hunt']) {
  for (const save of kind === 'plugin' ? [true, false] : [true]) {
    test(`${kind} survives navigation and reload with saving ${save ? 'enabled' : 'disabled'}`, async ({
      page,
      request,
    }) => {
      const fixture = await investigatorCases(request)
      const journey = executionJourney(kind, page, request, fixture, 'success', save)
      try {
        await loginUi(page, fixture.credentials)
        await journey.configure()
        const accepted = await journey.submit()
        await ready(fixture.marker)
        expect((await journey.read(accepted.links.detail)).status).toBe('running')
        const other = fixture.cases[1]
        await page.getByRole('combobox', { name: /Active case/ }).press('Enter')
        await page
          .getByRole('option', {
            name: new RegExp(other.case_number),
          })
          .click()
        await expect(page).toHaveURL(new RegExp(`/case/${other.id}/`))
        await page.getByRole('link', { name: 'Case overview', exact: true }).click()
        await expect(page).toHaveURL(new RegExp(`/case/${other.id}$`))
        await page.reload()
        await expect(
          page.getByRole('heading', { name: `Case: ${fixture.cases[1].case_number}`, exact: true }),
        ).toBeVisible()
        await release(fixture.marker)
        await expect
          .poll(async () => (await journey.read(accepted.links.detail)).status)
          .toBe('completed')
        await journey.reopen(accepted)
        expect((await journey.read(accepted.links.detail)).id).toBe(accepted.id)
        await journey.terminal(accepted, 'completed')
        await journey.retained(accepted)
        await journey.effects(save)
      } finally {
        await release(fixture.marker)
      }
    })
  }

  test(`${kind} confirms cancellation and retains prior output`, async ({ page, request }) => {
    const fixture = await investigatorCases(request)
    const journey = executionJourney(
      kind,
      page,
      request,
      fixture,
      kind === 'hunt' ? 'cancel' : 'success',
    )
    try {
      await loginUi(page, fixture.credentials)
      await journey.configure()
      const accepted = await journey.submit()
      await ready(fixture.marker)
      await expect
        .poll(async () => {
          if (kind === 'plugin') return (await journey.read(accepted.links.results)).items.length
          const detail = await journey.read(`${accepted.links.detail}?include_steps=true`)
          return detail.steps.filter((step) => step.status === 'completed').length
        })
        .toBeGreaterThan(0)
      await journey.reopen(accepted)
      await page
        .getByRole('button', {
          name: kind === 'plugin' ? 'Cancel execution' : 'Cancel Hunt',
          exact: true,
        })
        .click()
      await journey.terminal(accepted, 'cancelled')
      await page.reload()
      await journey.reopen(accepted)
      await journey.terminal(accepted, 'cancelled')
      await journey.retained(accepted)
      if (kind === 'hunt') {
        const detail = await journey.read(`${accepted.links.detail}?include_steps=true`)
        expect(detail.steps.find((step) => step.step_id === 'first').status).toBe('completed')
        expect(detail.steps.find((step) => step.step_id === 'never')?.started_at ?? null).toBeNull()
        expect(await starts(fixture.marker)).toBe(2)
      }
    } finally {
      await release(fixture.marker)
    }
  })

  test(`${kind} reopens failure information and partial results`, async ({ page, request }) => {
    const fixture = await investigatorCases(request)
    const journey = executionJourney(kind, page, request, fixture, 'error')
    try {
      await loginUi(page, fixture.credentials)
      await journey.configure()
      const accepted = await journey.submit()
      await ready(fixture.marker)
      await release(fixture.marker)
      await page.reload()
      await journey.reopen(accepted)
      await journey.terminal(accepted, kind === 'plugin' ? 'failed' : 'partial')
      await journey.retained(accepted)
      await expect(page.getByText(/Deterministic browser failure/).first()).toBeVisible()
      const detail = await journey.read(`${accepted.links.detail}?include_steps=true`)
      expect(JSON.stringify(kind === 'plugin' ? detail.error : detail.steps)).toContain(
        'Deterministic browser failure',
      )
    } finally {
      await release(fixture.marker)
    }
  })

  test(`${kind} recovers lost acceptance once and permits an intentional repeat`, async ({
    page,
    request,
  }) => {
    const fixture = await investigatorCases(request)
    const journey = executionJourney(kind, page, request, fixture)
    const pattern =
      kind === 'plugin'
        ? '**/api/plugins/BrowserExecutionPlugin/execute'
        : /\/api\/hunts\/\d+\/execute$/
    let accepted
    const dropAcceptance = async (route) => {
      // Forward the real POST first. Only its successful acceptance is dropped.
      const response = await route.fetch({ maxRetries: 0 })
      expect(response.status()).toBe(202)
      accepted = await json(response)
      await route.abort('failed')
    }
    try {
      await loginUi(page, fixture.credentials)
      await journey.configure()
      await page.route(pattern, dropAcceptance)
      await journey.clickSubmit()
      await expect(page.getByText(/submission response was uncertain/).first()).toBeVisible()
      await page.unroute(pattern, dropAcceptance)
      expect(accepted.id).toBeTruthy()
      await ready(fixture.marker)
      await page.reload()
      await journey.configure()
      const recovered = await journey.submit()
      expect(recovered.id).toBe(accepted.id)
      await release(fixture.marker)
      await journey.reopen(recovered)
      await journey.terminal(recovered, 'completed')
      await journey.retained(recovered)
      const originalEffects = await journey.effects(true)
      expect((await journey.history()).map((item) => item.id)).toEqual([accepted.id])
      expect(await starts(fixture.marker)).toBe(1)
      await journey.configure()
      const repeated = await journey.submit()
      expect(repeated.id).not.toBe(accepted.id)
      await journey.reopen(repeated, true)
      await journey.terminal(repeated, 'completed')
      expect((await journey.history()).map((item) => item.id).sort()).toEqual(
        [accepted.id, repeated.id].sort(),
      )
      expect(await starts(fixture.marker)).toBe(2)
      const evidence = await journey.read(`/api/evidence/case/${fixture.cases[0].id}`)
      expect(evidence.filter((item) => !item.is_folder)).toHaveLength(
        originalEffects.evidence.filter((item) => !item.is_folder).length + 1,
      )
    } finally {
      await page.unroute(pattern, dropAcceptance)
      await release(fixture.marker)
    }
  })
}
