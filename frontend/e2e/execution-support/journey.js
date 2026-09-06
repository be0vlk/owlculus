import process from 'node:process'
import { access, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { expect } from '@playwright/test'
import { json } from '../support/workflow'

export async function release(marker) {
  await writeFile(path.join(process.env.OWLCULUS_EXECUTION_CONTROLS, `${marker}.release`), '')
}

export async function ready(marker) {
  await expect
    .poll(
      async () => {
        try {
          await access(path.join(process.env.OWLCULUS_EXECUTION_CONTROLS, `${marker}.ready`))
          return true
        } catch {
          return false
        }
      },
      { timeout: 45_000 },
    )
    .toBe(true)
}

export async function starts(marker) {
  return (
    await readFile(path.join(process.env.OWLCULUS_EXECUTION_CONTROLS, `${marker}.starts`), 'utf8')
  )
    .trim()
    .split('\n').length
}

export function executionJourney(kind, page, request, fixture, mode = 'success', save = true) {
  const caseId = fixture.cases[0].id
  const route = `/case/${caseId}/${kind === 'plugin' ? 'plugins' : 'hunts'}`
  const huntName = `Browser ${mode} hunt`
  const read = async (url) => json(await request.get(url, { headers: fixture.headers }))
  const acceptance = (response) =>
    response.request().method() === 'POST' &&
    new URL(response.url()).pathname.match(
      kind === 'plugin'
        ? /^\/api\/plugins\/BrowserExecutionPlugin\/execute$/
        : /^\/api\/hunts\/\d+\/execute$/,
    )

  async function configure() {
    await page.goto(route)
    if (kind === 'plugin') {
      await page
        .getByRole('button', { name: 'Configure Browser execution provider', exact: true })
        .click()
      await page.getByLabel('Marker', { exact: true }).fill(fixture.marker)
      await page.getByLabel('Barrier', { exact: true }).fill(fixture.marker)
      await page.getByLabel('Mode', { exact: true }).fill(mode)
      await page.getByLabel('Save to case evidence', { exact: true }).setChecked(save)
    } else {
      await page
        .locator('.hunt-card')
        .filter({ hasText: huntName })
        .getByRole('button', { name: 'Execute Hunt', exact: true })
        .click()
      const dialog = page.getByRole('dialog', { name: 'Execute Hunt', exact: true })
      await dialog.getByLabel('Marker *', { exact: true }).fill(fixture.marker)
      await dialog.getByLabel('Barrier *', { exact: true }).fill(fixture.marker)
    }
  }

  async function clickSubmit() {
    const container =
      kind === 'plugin' ? page : page.getByRole('dialog', { name: 'Execute Hunt', exact: true })
    await container
      .getByRole('button', {
        name: kind === 'plugin' ? 'Execute Plugin' : 'Execute Hunt',
        exact: true,
      })
      .click()
  }

  async function submit() {
    const response = page.waitForResponse(acceptance)
    await clickSubmit()
    const accepted = await response
    expect(accepted.status()).toBe(202)
    return json(accepted)
  }

  async function reopen(accepted, fromActivity = false) {
    await page.goto(route)
    if (kind === 'plugin') {
      const detailResponse = page.waitForResponse(
        (response) =>
          new URL(response.url()).pathname === accepted.links.detail &&
          response.request().method() === 'GET',
      )
      await page
        .getByRole('list', { name: 'Plugin execution history' })
        .getByText('BrowserExecutionPlugin', { exact: true })
        .first()
        .click()
      expect((await json(await detailResponse)).id).toBe(accepted.id)
    } else {
      const state = await read(accepted.links.detail)
      if (fromActivity || ['pending', 'running'].includes(state.status)) {
        await page.getByRole('tab', { name: /Active Executions/ }).click()
        await page
          .locator('.hunt-progress-card')
          .filter({ hasText: new RegExp(`Execution #${accepted.id}\\b`) })
          .getByRole('button', { name: /^(View )?(Details|Results)$/ })
          .click()
      } else {
        await page.getByRole('tab', { name: 'Execution History', exact: true }).click()
        await page
          .getByRole('button', { name: `View ${huntName} execution`, exact: true })
          .first()
          .click()
      }
      await expect(page).toHaveURL(new RegExp(`/hunts/execution/${accepted.id}$`))
    }
  }

  async function terminal(accepted, status) {
    await expect
      .poll(async () => (await read(accepted.links.detail)).status, { timeout: 45_000 })
      .toBe(status)
    if (kind === 'plugin') {
      await expect(
        page
          .getByRole('region', { name: 'Selected plugin execution' })
          .getByRole('status')
          .filter({ hasText: 'BrowserExecutionPlugin' }),
      ).toContainText(status)
    } else {
      await expect(
        page
          .getByText(
            status === 'partial' ? 'Partial Success' : status[0].toUpperCase() + status.slice(1),
            {
              exact: true,
            },
          )
          .first(),
      ).toBeVisible()
    }
  }

  async function retained(accepted) {
    if (kind === 'plugin') {
      const results = await read(accepted.links.results)
      expect(results.items).toContainEqual({
        type: 'data',
        data: { finding: `Retained ${fixture.marker}`, case_id: caseId },
      })
      await page.getByRole('button', { name: 'View retained results', exact: true }).click()
      await expect(page.getByRole('dialog', { name: 'Plugin results' })).toContainText(
        `Retained ${fixture.marker}`,
      )
      await page.getByRole('button', { name: 'Close plugin results', exact: true }).click()
    } else {
      const detail = await read(`${accepted.links.detail}?include_steps=true`)
      expect(JSON.stringify(detail.steps[0].output)).toContain(`Retained ${fixture.marker}`)
      await page.getByRole('button', { name: /Step 1: BrowserExecutionPlugin/ }).click()
      await expect(page.getByText(`Retained ${fixture.marker}`, { exact: true })).toBeVisible()
    }
  }

  async function effects(expectedSaved) {
    const original = fixture.cases[0].id
    const evidence = await read(`/api/evidence/case/${original}`)
    const entities = await read(`/api/cases/${original}/entities`)
    if (expectedSaved) {
      const files = evidence.filter((item) => !item.is_folder)
      expect(files).toHaveLength(1)
      expect(files[0].case_id).toBe(original)
      expect(entities).toHaveLength(1)
      expect(entities[0].data.ip_address).toBe('192.0.2.10')
      expect(JSON.stringify(entities)).toContain(fixture.marker)
    } else {
      expect(evidence).toEqual([])
      expect(entities).toEqual([])
    }
    expect(await read(`/api/evidence/case/${fixture.cases[1].id}`)).toEqual([])
    expect(await read(`/api/cases/${fixture.cases[1].id}/entities`)).toEqual([])
    return { evidence, entities }
  }

  async function history() {
    const data = await read(
      kind === 'plugin'
        ? `/api/plugins/executions/case/${caseId}`
        : `/api/hunts/cases/${caseId}/executions`,
    )
    return kind === 'plugin' ? data.items : data
  }

  return {
    configure,
    clickSubmit,
    submit,
    reopen,
    terminal,
    retained,
    effects,
    history,
    read,
    acceptance,
  }
}
