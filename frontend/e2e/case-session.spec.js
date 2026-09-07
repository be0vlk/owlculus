import process from 'node:process'
import { expect } from '@playwright/test'
import { administrator, bootstrap, json, loginUi } from './support/workflow'
import {
  test,
  caseWorkspace,
  createUser,
  switchCase,
  notesVisible,
  tasksVisible,
  persistedWorkspace,
  caseRead,
  taskList,
} from './support/case-session'

test.use({ trace: 'retain-on-failure', screenshot: 'only-on-failure' })
test.beforeAll(async ({ request }) => bootstrap(request))

test('switches real Case notes and Tasks with durable ownership', async ({ page, request }) => {
  const {
    credentials,
    headers,
    cases: [original, other],
  } = await caseWorkspace(request)
  await loginUi(page, credentials)
  await page.goto(`/case/${original.id}?tab=notes`)
  await notesVisible(page, original, other)
  await switchCase(page, other)
  await notesVisible(page, other, original)
  await page.reload()
  await notesVisible(page, other, original)
  await page.getByRole('link', { name: 'Tasks', exact: true }).click()
  await tasksVisible(page, other, original)
  await switchCase(page, original)
  await tasksVisible(page, original, other)
  await page.reload()
  await tasksVisible(page, original, other)
  await expect(page).toHaveURL(new RegExp(`/case/${original.id}/tasks$`))
  for (const record of [original, other]) await persistedWorkspace(request, headers, record)
})

for (const { boundary, suffix, match, visible, expected } of [
  {
    boundary: 'notes',
    suffix: '?tab=notes',
    match: caseRead,
    visible: notesVisible,
    expected: (record) =>
      expect.objectContaining({ id: record.id, notes: `<p>${record.notes}</p>` }),
  },
  {
    boundary: 'Tasks',
    suffix: '/tasks',
    match: taskList,
    visible: tasksVisible,
    expected: (record) =>
      expect.arrayContaining([expect.objectContaining({ id: record.task.id, case_id: record.id })]),
  },
]) {
  test(`late real ${boundary} response cannot replace the selected Case`, async ({
    page,
    request,
    holdResponse,
  }) => {
    const {
      credentials,
      headers,
      cases: [original, other],
    } = await caseWorkspace(request)
    await loginUi(page, credentials)
    await page.goto(`/case/${other.id}${suffix}`)
    const hold = await holdResponse(match(original))
    await switchCase(page, original)
    expect(await hold.ready).toEqual(expected(original))
    await switchCase(page, other)
    await visible(page, other, original)
    hold.release()
    await hold.done
    await visible(page, other, original)
    for (const record of [original, other]) await persistedWorkspace(request, headers, record)
  })
}

test('accepted notes write stays in its original Case after a delayed acknowledgement', async ({
  page,
  request,
  holdResponse,
}) => {
  const {
    credentials,
    headers,
    cases: [original, other],
  } = await caseWorkspace(request)
  await loginUi(page, credentials)
  await page.goto(`/case/${original.id}?tab=notes`)
  await notesVisible(page, original, other)
  await page.getByRole('button', { name: 'Edit Notes', exact: true }).click()
  const draft = `${original.title} acknowledged draft`
  await page.getByRole('textbox', { name: 'Case notes', exact: true }).fill(draft)
  const hold = await holdResponse(
    (request) =>
      request.method() === 'PUT' && new URL(request.url()).pathname === `/api/cases/${original.id}`,
  )
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  expect(await hold.ready).toMatchObject({ id: original.id, notes: `<p>${draft}</p>` })
  await persistedWorkspace(request, headers, { ...original, notes: draft })
  await switchCase(page, other)
  await notesVisible(page, other, original)
  hold.release()
  await hold.done
  await notesVisible(page, other, { notes: draft })
  await page.getByRole('button', { name: 'Edit Notes', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Case notes', exact: true })).toHaveText(
    other.notes,
  )
  await persistedWorkspace(request, headers, other)
  await page.reload()
  await notesVisible(page, other, { notes: draft })
  await switchCase(page, original)
  await notesVisible(page, { notes: draft }, other)
})

test('assigned Analyst reads Case data while unassigned direct links are denied without logout', async ({
  page,
  request,
}) => {
  const {
    credentials,
    headers,
    cases: [assigned, other],
  } = await caseWorkspace(request, 'Analyst')
  const protectedWorkspace = await caseWorkspace(request)
  const protectedCase = protectedWorkspace.cases[0]
  await loginUi(page, credentials)
  await page.goto(`/case/${assigned.id}?tab=notes`)
  await notesVisible(page, assigned, other)
  await page.getByRole('link', { name: 'Tasks', exact: true }).click()
  await tasksVisible(page, assigned, other)
  await persistedWorkspace(request, headers, assigned)
  for (const path of [
    `/api/cases/${protectedCase.id}`,
    `/api/tasks/${protectedCase.task.id}`,
    `/api/tasks/?case_id=${protectedCase.id}`,
  ]) {
    const denied = await request.get(path, { headers })
    expect(denied.status()).toBe(403)
    expect(await denied.text()).not.toContain(protectedCase.notes)
    expect(await denied.text()).not.toContain(protectedCase.task.title)
  }
  for (const path of [
    `/case/${protectedCase.id}?tab=notes`,
    `/case/${protectedCase.id}/tasks/${protectedCase.task.id}`,
    `/tasks/${protectedCase.task.id}`,
  ]) {
    await page.goto(path)
    await expect(page).not.toHaveURL(/\/login/)
    await expect(page.getByRole('combobox', { name: /^Active case:/ })).toBeVisible()
    await expect(page.getByText(protectedCase.notes, { exact: true })).toHaveCount(0)
    await expect(
      page.getByRole('heading', { name: `Task: ${protectedCase.task.title}`, exact: true }),
    ).toHaveCount(0)
  }
  await page.goto(`/case/${assigned.id}?tab=notes`)
  await notesVisible(page, assigned, protectedCase)
  expect(await json(await request.get('/api/users/me', { headers }))).toMatchObject({
    username: credentials.username,
  })
})

test('membership loss rejects the next request and late data cannot restore the workspace', async ({
  page,
  request,
  holdResponse,
}) => {
  const {
    credentials,
    headers,
    user,
    admin,
    cases: [original, other],
  } = await caseWorkspace(request)
  await loginUi(page, credentials)
  await page.goto(`/case/${original.id}?tab=notes`)
  await notesVisible(page, original, other)
  const hold = await holdResponse(taskList(original))
  await page.getByRole('link', { name: 'Tasks', exact: true }).click()
  expect(await hold.ready).toEqual(
    expect.arrayContaining([expect.objectContaining({ id: original.task.id })]),
  )
  await json(await request.delete(`/api/cases/${original.id}/users/${user.id}`, { headers: admin }))
  expect((await request.get(`/api/cases/${original.id}`, { headers })).status()).toBe(403)
  expect((await request.get(`/api/tasks/${original.task.id}`, { headers })).status()).toBe(403)
  const rejected = page.waitForResponse(
    (response) => caseRead(original)(response.request()) && response.status() === 403,
  )
  await page.getByRole('link', { name: 'Dashboard', exact: true }).click()
  await rejected
  await expect(page).toHaveURL(new RegExp(`/case/${other.id}$`))
  await expect(page.getByRole('combobox', { name: /^Active case:/ })).toHaveValue(
    `${other.case_number} — ${other.title} (${other.status})`,
  )
  await page.getByRole('link', { name: 'Tasks', exact: true }).click()
  await tasksVisible(page, other, original)
  hold.release()
  await hold.done
  await tasksVisible(page, other, original)
  await expect(page.getByText(original.notes, { exact: true })).toHaveCount(0)
  await page.reload()
  await tasksVisible(page, other, original)
})

test('expired signed credential clears authentication and Case context', async ({
  page,
  request,
}) => {
  const {
    cases: [original],
  } = await caseWorkspace(request)
  expect(
    process.env.OWLCULUS_EXPIRED_TOKEN,
    'Runner must seed an expired signed credential',
  ).toBeTruthy()
  await loginUi(page, administrator)
  await page.goto(`/case/${original.id}?tab=notes`)
  await expect(page.getByText(original.notes, { exact: true })).toBeVisible()
  const token = process.env.OWLCULUS_EXPIRED_TOKEN
  expect(
    (
      await request.get('/api/users/me', { headers: { Authorization: `bearer ${token}` } })
    ).status(),
  ).toBe(401)
  await page.evaluate((expired) => localStorage.setItem('access_token', expired), token)
  const rejected = page.waitForResponse(
    (response) => new URL(response.url()).pathname.startsWith('/api/') && response.status() === 401,
  )
  await page.getByRole('link', { name: 'Tasks', exact: true }).click()
  await rejected
  await expect(page).toHaveURL(/\/login/)
  expect(await page.evaluate(() => localStorage.getItem('access_token'))).toBeNull()
  await expect(page.getByRole('combobox', { name: /^Active case:/ })).toHaveCount(0)
  await expect(page.getByText(original.notes, { exact: true })).toHaveCount(0)
  await page.reload()
  await expect(page).toHaveURL(/\/login/)
})

test('account change excludes former Case data through late response Back and reload', async ({
  page,
  request,
  holdResponse,
}) => {
  const first = await caseWorkspace(request)
  const second = await caseWorkspace(request)
  const original = first.cases[0]
  const other = second.cases[0]
  await loginUi(page, first.credentials)
  await page.goto(`/case/${original.id}?tab=notes`)
  await expect(page.getByText(original.notes, { exact: true })).toBeVisible()
  const hold = await holdResponse(taskList(original))
  await page.getByRole('link', { name: 'Tasks', exact: true }).click()
  expect(await hold.ready).toEqual(
    expect.arrayContaining([expect.objectContaining({ id: original.task.id })]),
  )
  await page.getByRole('button', { name: 'Logout', exact: true }).click()
  await expect(page).toHaveURL(/\/login/)
  // Submit in the same document so the former session's request stays in flight.
  await page.getByLabel('Username', { exact: true }).fill(second.credentials.username)
  await page.getByLabel('Password', { exact: true }).fill(second.credentials.password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page).toHaveURL(/\/cases$/)
  await switchCase(page, other)
  await page.getByRole('link', { name: 'Tasks', exact: true }).click()
  await tasksVisible(page, other, original)
  hold.release()
  await hold.done
  await tasksVisible(page, other, original)
  // Back through login history must settle on this account's dashboard.
  for (let step = 0; step < 2; step++) {
    await page.goBack()
    await expect(page).toHaveURL(/\/cases$/)
    await expect(page.getByRole('cell', { name: other.case_number, exact: true })).toBeVisible()
    await expect(page.getByText(original.notes, { exact: true })).toHaveCount(0)
    await expect(page.getByRole('link', { name: original.task.title, exact: true })).toHaveCount(0)
  }
  await expect(page.getByText(original.notes, { exact: true })).toHaveCount(0)
  await expect(page.getByRole('link', { name: original.task.title, exact: true })).toHaveCount(0)
  await page.reload()
  const accessible = await json(await request.get('/api/cases/', { headers: second.headers }))
  expect(accessible.map((record) => record.id).sort()).toEqual(
    second.cases.map((record) => record.id).sort(),
  )
  await page.getByRole('combobox', { name: /^Active case:/ }).press('ArrowDown')
  await expect(page.getByRole('option', { name: new RegExp(original.case_number) })).toHaveCount(0)
  await page.getByRole('combobox', { name: /^Active case:/ }).press('Escape')
  await switchCase(page, other)
  await page.getByRole('link', { name: 'Tasks', exact: true }).click()
  await tasksVisible(page, other, original)
})

test('Case lead assigns a Task and another Investigator completes the persisted handoff', async ({
  page,
  request,
  browser,
}) => {
  const lead = await caseWorkspace(request)
  const assignedCase = lead.cases[0]
  const assignee = await createUser(request)
  await json(
    await request.post(`/api/cases/${assignedCase.id}/users/${assignee.user.id}`, {
      headers: lead.admin,
    }),
  )
  await loginUi(page, lead.credentials)
  await page.goto(`/case/${assignedCase.id}/tasks`)
  await page.getByRole('button', { name: 'New Task', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Create Task', exact: true })
  const title = `${assignedCase.title} handoff`
  await dialog.getByLabel('Title', { exact: true }).fill(title)
  await dialog
    .getByLabel('Description', { exact: true })
    .fill('Verify the source and complete this review')
  await dialog.getByRole('combobox', { name: 'Assign To', exact: true }).press('ArrowDown')
  await page.getByRole('option', { name: assignee.credentials.username, exact: true }).click()
  const created = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/tasks/',
  )
  await dialog.getByRole('button', { name: 'Create', exact: true }).click()
  const task = await json(await created)
  expect(task).toMatchObject({
    case_id: assignedCase.id,
    assigned_to_id: assignee.user.id,
    assigned_by_id: lead.user.id,
    title,
  })
  await expect(dialog).toBeHidden()
  const context = await browser.newContext({ viewport: page.viewportSize() })
  const investigator = await context.newPage()
  try {
    await loginUi(investigator, assignee.credentials)
    await investigator.getByRole('link', { name: 'Tasks', exact: true }).click()
    await expect(investigator.getByRole('link', { name: title, exact: true })).toBeVisible()
    await investigator.reload()
    await investigator
      .getByRole('button', { name: `Update status for ${title}`, exact: true })
      .click()
    const statusDialog = investigator.getByRole('dialog', { name: 'Update Status', exact: true })
    await statusDialog.getByRole('combobox', { name: 'New Status', exact: true }).press('ArrowDown')
    await investigator.getByRole('option', { name: 'Completed', exact: true }).click()
    const completed = investigator.waitForResponse(
      (response) =>
        response.request().method() === 'PUT' &&
        new URL(response.url()).pathname === `/api/tasks/${task.id}/status`,
    )
    await statusDialog.getByRole('button', { name: 'Update', exact: true }).click()
    expect(await json(await completed)).toMatchObject({
      id: task.id,
      status: 'completed',
      assigned_to_id: assignee.user.id,
    })
    await expect(statusDialog).toBeHidden()
    for (const sessionPage of [investigator, page]) {
      await sessionPage.reload()
      await sessionPage.getByText('All Tasks', { exact: true }).click()
      await expect(
        sessionPage
          .getByRole('row')
          .filter({ has: sessionPage.getByRole('link', { name: title, exact: true }) }),
      ).toContainText('Completed')
    }
    for (const headers of [lead.headers, assignee.headers]) {
      expect(await json(await request.get(`/api/tasks/${task.id}`, { headers }))).toMatchObject({
        id: task.id,
        case_id: assignedCase.id,
        assigned_to_id: assignee.user.id,
        status: 'completed',
      })
    }
  } finally {
    // Playwright records every context in the retained failure trace automatically.
    try {
      await investigator
        .screenshot({ path: test.info().outputPath('assignee.png') })
        .catch((error) => {
          test.info().annotations.push({ type: 'artifact-error', description: error.message })
        })
    } finally {
      await context.close()
    }
  }
})
