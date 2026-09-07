import { randomUUID } from 'node:crypto'
import { expect, test } from '@playwright/test'
import {
  administrator,
  adminHeaders,
  bootstrap,
  createCase,
  json,
  loginUi,
} from './support/workflow'

test.beforeAll(async ({ request }) => bootstrap(request))

test('bulk assigns and updates selected Tasks with persistence after refresh', async ({
  page,
  request,
}) => {
  const headers = await adminHeaders(request)
  const assignedCase = await createCase(request, headers, `Bulk Tasks ${randomUUID()}`)
  const owner = await json(await request.get('/api/users/me', { headers }))
  await json(await request.post(`/api/cases/${assignedCase.id}/users/${owner.id}`, { headers }))
  const tasks = []
  for (const title of ['Review first evidence', 'Review second evidence']) {
    tasks.push(
      await json(
        await request.post('/api/tasks/', {
          headers,
          data: { case_id: assignedCase.id, title, description: 'Bulk browser workflow' },
        }),
      ),
    )
  }
  await loginUi(page, administrator)
  await page.goto(`/case/${assignedCase.id}/tasks`)
  await page.getByText('All Tasks', { exact: true }).click()
  await expect(page.getByRole('cell', { name: tasks[0].title, exact: true })).toBeVisible()
  await page.locator('thead').getByRole('checkbox').check()
  await expect(page.getByText('2 Tasks selected', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Bulk Assign', exact: true }).click()
  const assign = page.getByRole('dialog', { name: 'Bulk Assign', exact: true })
  await assign.getByLabel('Assign To', { exact: true }).press('Enter')
  await page.getByRole('option', { name: owner.username, exact: true }).click()
  await assign.getByRole('button', { name: 'Apply', exact: true }).press('Enter')
  await expect(assign).toBeHidden()
  await expect(page.getByRole('cell', { name: owner.username, exact: true })).toHaveCount(2)
  await expect(page.getByRole('button', { name: 'Refresh tasks', exact: true })).toBeFocused()
  await page.locator('thead').getByRole('checkbox').check()
  await page.getByRole('button', { name: 'Bulk Update Status', exact: true }).click()
  const status = page.getByRole('dialog', { name: 'Bulk Update Status', exact: true })
  await status.getByLabel('New Status', { exact: true }).press('Enter')
  await page.getByRole('option', { name: 'Completed', exact: true }).click()
  await status.getByRole('button', { name: 'Apply', exact: true }).press('Enter')
  await expect(status).toBeHidden()
  await page.reload()
  await expect(page.getByRole('cell', { name: 'Completed', exact: true })).toHaveCount(2)
  await expect(page.getByRole('cell', { name: owner.username, exact: true })).toHaveCount(2)
  for (const task of tasks) {
    const saved = await json(await request.get(`/api/tasks/${task.id}`, { headers }))
    expect(saved).toMatchObject({
      assigned_to_id: owner.id,
      status: 'completed',
      case_id: assignedCase.id,
    })
  }
})
