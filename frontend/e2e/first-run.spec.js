import process from 'node:process'
import { readFile, writeFile } from 'node:fs/promises'
import { basename } from 'node:path'
import { expect, test } from '@playwright/test'
import { browserViewports } from './viewports'

const administrator = {
  username: 'e2e_admin',
  email: 'e2e-admin@example.org',
  password: 'E2ePassword123!',
}

function requestMatches(request, method, pathname) {
  return request.method() === method && new URL(request.url()).pathname === pathname
}

function websocketOrigin(url) {
  const parsedUrl = new URL(url)
  parsedUrl.protocol = parsedUrl.protocol === 'wss:' ? 'https:' : 'http:'
  return parsedUrl.origin
}

function visibleAlert(page, message) {
  return page.getByRole('alert').filter({ hasText: message })
}

async function exerciseTextInput(input) {
  await expect(input).toBeVisible()
  await expect(input).toBeEnabled()
  await input.fill('migration smoke')
  await expect(input).toHaveValue('migration smoke')
  await input.clear()
}

async function exerciseCaseAndEntityWorkflow(page) {
  const openNewCaseButton = page.getByRole('button', { name: 'New Case', exact: true })
  await openNewCaseButton.click()
  let newCaseDialog = page.getByRole('dialog', { name: 'New Case', exact: true })
  await expect(newCaseDialog).toBeVisible()
  await expect(newCaseDialog.getByLabel('Title', { exact: true })).toBeFocused()
  await page.keyboard.press('Shift+Tab')
  await expect(newCaseDialog.locator(':focus')).toHaveCount(1)
  await page.keyboard.press('Escape')
  await expect(newCaseDialog).toBeHidden()
  await expect(openNewCaseButton).toBeFocused()

  await openNewCaseButton.click()
  newCaseDialog = page.getByRole('dialog', { name: 'New Case', exact: true })
  const caseTitle = newCaseDialog.getByLabel('Title', { exact: true })
  await expect(caseTitle).toBeFocused()
  await caseTitle.fill('Migration Safety Case')
  const clientSelect = newCaseDialog.getByLabel('Client', { exact: true })
  await clientSelect.focus()
  await clientSelect.press('ArrowDown')
  await page.getByRole('option', { name: 'Migration Safety Client', exact: true }).click()
  await newCaseDialog.getByRole('button', { name: 'Create Case', exact: true }).click()
  await expect(newCaseDialog).toBeHidden()

  const caseRow = page.getByRole('row').filter({ hasText: 'Migration Safety Case' })
  await expect(caseRow).toContainText('Migration Safety Client')
  await caseRow.click()
  await expect(page).toHaveURL(/\/case\/\d+$/)
  await expect(page.getByText('Case Information', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Edit Case', exact: true }).click()
  const editCaseDialog = page.getByRole('dialog', { name: 'Edit Case', exact: true })
  await editCaseDialog
    .getByLabel('Case Title', { exact: true })
    .fill('Migration Safety Case Updated')
  await editCaseDialog.getByRole('button', { name: 'Save Changes', exact: true }).click()
  await expect(editCaseDialog).toBeHidden()
  await expect(page.getByText('Migration Safety Case Updated', { exact: true })).toBeVisible()

  const evidenceTab = page.getByRole('tab', { name: 'Evidence', exact: true })
  await evidenceTab.click()
  await expect(evidenceTab).toHaveAttribute('aria-selected', 'true')
  await expect(page).toHaveURL(/[?&]tab=evidence(?:&|$)/)

  const entitiesTab = page.getByRole('tab', { name: 'Entities', exact: true })
  await entitiesTab.click()
  await expect(entitiesTab).toHaveAttribute('aria-selected', 'true')
  await expect(page).not.toHaveURL(/[?&]tab=/)

  await expect(page.getByText('No Entities Found', { exact: true })).toBeVisible()
  const openNewEntityButton = page.getByRole('button', { name: 'Add Entity', exact: true })
  await openNewEntityButton.click()
  let newEntityDialog = page.getByRole('dialog', { name: 'Add New Entity', exact: true })
  await expect(newEntityDialog.getByLabel('First Name', { exact: true })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(newEntityDialog).toBeHidden()
  await expect(openNewEntityButton).toBeFocused()

  await openNewEntityButton.click()
  newEntityDialog = page.getByRole('dialog', { name: 'Add New Entity', exact: true })
  const addEntityButton = newEntityDialog.getByRole('button', {
    name: 'Add Entity',
    exact: true,
  })
  await expect(addEntityButton).toBeDisabled()
  const firstName = newEntityDialog.getByLabel('First Name', { exact: true })
  const lastName = newEntityDialog.getByLabel('Last Name', { exact: true })
  await expect(firstName).toBeFocused()
  await firstName.fill('Ada')
  await lastName.fill('Lovelace')
  await expect(addEntityButton).toBeEnabled()
  await lastName.press('Enter')

  const createdDialog = page.getByRole('dialog', {
    name: 'Entity Created Successfully',
    exact: true,
  })
  await expect(createdDialog).toContainText('Ada Lovelace')
  await createdDialog.getByRole('button', { name: 'No, thanks', exact: true }).click()
  await expect(openNewEntityButton).toBeFocused()

  let entityRow = page.getByRole('row').filter({ hasText: 'Ada Lovelace' })
  await expect(entityRow).toBeVisible()
  await page.getByLabel('Search entities', { exact: true }).fill('missing identity')
  await expect(page.getByText('No entities found matching "missing identity"')).toBeVisible()
  await page.getByLabel('Search entities', { exact: true }).clear()
  await expect(entityRow).toBeVisible()

  await page.getByRole('button', { name: 'View Ada Lovelace', exact: true }).click()
  const entityDialog = page.getByRole('dialog', { name: 'Ada Lovelace', exact: true })
  await expect(entityDialog).toBeVisible()
  await entityDialog.getByRole('button', { name: 'Edit Entity', exact: true }).click()
  await entityDialog.getByLabel('First Name', { exact: true }).fill('Grace')
  await entityDialog.getByRole('button', { name: 'Save Changes', exact: true }).click()
  const updatedEntityDialog = page.getByRole('dialog', { name: 'Grace Lovelace', exact: true })
  await expect(updatedEntityDialog).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(updatedEntityDialog).toBeHidden()
  await expect(page.getByRole('button', { name: 'View Grace Lovelace', exact: true })).toBeFocused()

  entityRow = page.getByRole('row').filter({ hasText: 'Grace Lovelace' })
  await expect(entityRow).toBeVisible()
  await page.getByRole('button', { name: 'Delete Grace Lovelace', exact: true }).click()
  const deleteDialog = page.getByRole('dialog', { name: 'Confirm Delete', exact: true })
  await expect(deleteDialog).toContainText('This action cannot be undone.')
  await deleteDialog.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expect(entityRow).toBeVisible()
}

function observeBrowserRuntime(page, { expectedConsoleErrors = [] } = {}) {
  const browserOrigin = new URL(process.env.OWLCULUS_BASE_URL).origin
  const preflightRequests = []
  const unsafeRequests = []
  const failedRequests = []
  const browserErrors = []
  const uncaughtErrors = []
  const viteHmrConnections = []
  const viteHmrUpdates = []
  let hotReloadVerificationRequested = false

  page.on('request', (request) => {
    const requestUrl = new URL(request.url())

    if (request.method() === 'OPTIONS') {
      preflightRequests.push(request.url())
    }

    if (requestUrl.port === '8000' || requestUrl.origin !== browserOrigin) {
      unsafeRequests.push(request.url())
    }
  })

  page.on('websocket', (websocket) => {
    const websocketUrl = new URL(websocket.url())
    if (websocketUrl.port === '8000' || websocketOrigin(websocket.url()) !== browserOrigin) {
      unsafeRequests.push(websocket.url())
    }
    websocket.on('socketerror', (error) => {
      failedRequests.push(`${websocket.url()}: ${error}`)
    })
    websocket.on('framereceived', ({ payload }) => {
      if (process.env.OWLCULUS_SERVER_KIND !== 'vite' || typeof payload !== 'string') return

      try {
        const message = JSON.parse(payload)
        if (message.type === 'connected') {
          viteHmrConnections.push(websocket.url())
        }
        if (message.type === 'update') {
          viteHmrUpdates.push(...message.updates)
        }
      } catch {
        // Non-JSON application WebSocket frames are unrelated to Vite's HMR protocol.
      }
    })
  })

  page.on('requestfailed', (request) => {
    failedRequests.push(`${request.url()}: ${request.failure()?.errorText || 'unknown failure'}`)
  })

  page.on('console', (message) => {
    if (message.type() === 'error') {
      browserErrors.push({ message: message.text(), sourceUrl: message.location().url })
    }
  })

  page.on('pageerror', (error) => {
    uncaughtErrors.push(error.message)
  })

  return {
    async verifyViteHotReload() {
      if (process.env.OWLCULUS_SERVER_KIND !== 'vite') return

      const hmrProbeFilePath = process.env.OWLCULUS_HMR_PROBE_PATH
      if (!hmrProbeFilePath) {
        throw new Error('OWLCULUS_HMR_PROBE_PATH must be provided for the Vite journey')
      }
      const hmrProbeModulePath = `/src/${basename(hmrProbeFilePath)}`
      hotReloadVerificationRequested = true
      const baselineSource = await readFile(hmrProbeFilePath, 'utf8')
      await page.evaluate((modulePath) => import(modulePath), hmrProbeModulePath)
      await expect(page.locator('html')).toHaveAttribute('data-e2e-hmr-probe', 'baseline')

      const activeSource = baselineSource.replace("marker = 'baseline'", "marker = 'active'")
      if (activeSource === baselineSource) {
        throw new Error('Unable to update the HMR probe marker')
      }
      await writeFile(hmrProbeFilePath, activeSource)
      await expect
        .poll(
          () =>
            viteHmrUpdates.some(({ path, acceptedPath }) =>
              [path, acceptedPath].some((modulePath) => modulePath?.includes(hmrProbeModulePath)),
            ),
          {
            message: 'the browser should receive an update for the HMR probe module',
            timeout: 15_000,
          },
        )
        .toBe(true)
      await expect(page.locator('html')).toHaveAttribute('data-e2e-hmr-probe', 'active')
    },
    assertSafeTraffic() {
      const unexpectedBrowserErrors = [...browserErrors]
      for (const expectedError of expectedConsoleErrors) {
        const expectedErrorIndex = unexpectedBrowserErrors.findIndex(
          ({ message, sourceUrl }) =>
            expectedError.message.test(message) &&
            sourceUrl &&
            new URL(sourceUrl).pathname === expectedError.pathname,
        )
        expect(
          expectedErrorIndex,
          `expected a console error from ${expectedError.pathname} matching ${expectedError.message}`,
        ).not.toBe(-1)
        unexpectedBrowserErrors.splice(expectedErrorIndex, 1)
      }

      expect(preflightRequests, 'browser should not make CORS preflight requests').toEqual([])
      expect(unsafeRequests, 'browser requests should stay on the page origin').toEqual([])
      expect(failedRequests, 'browser requests should not fail').toEqual([])
      expect(unexpectedBrowserErrors, 'browser console should have no unexpected errors').toEqual(
        [],
      )
      expect(uncaughtErrors, 'browser should have no uncaught exceptions').toEqual([])
      if (process.env.OWLCULUS_SERVER_KIND !== 'vite') return

      expect(
        viteHmrConnections,
        'the development server should complete the Vite HMR handshake',
      ).not.toEqual([])
      if (hotReloadVerificationRequested) {
        expect(viteHmrUpdates, 'the browser should receive a Vite HMR update').not.toEqual([])
      }
    },
  }
}

async function logIn(page) {
  await page.goto('/login')
  await page.getByLabel('Username', { exact: true }).fill(administrator.username)
  await page.getByLabel('Password', { exact: true }).fill(administrator.password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/cases$/)
  await expect(page.getByText('Case Management')).toBeVisible()
}

async function expectSetupForm(page) {
  await expect(page).toHaveURL(/\/setup$/)
  await expect(page.getByRole('heading', { name: 'Welcome to Owlculus' })).toBeVisible()
  await expect(page.getByText('Create your administrator account to get started')).toBeVisible()

  const expectedLabels = ['Setup Token', 'Username', 'Email', 'Password', 'Confirm Password']
  const inputs = expectedLabels.map((label) => page.getByLabel(label, { exact: true }))

  for (const input of inputs) {
    await expect(input).toBeVisible()
  }

  const verticalPositions = await Promise.all(
    inputs.map(async (input) => (await input.boundingBox())?.y ?? Number.POSITIVE_INFINITY),
  )
  expect(verticalPositions).toEqual([...verticalPositions].sort((left, right) => left - right))

  await expect(inputs[0]).toBeFocused()
  await expect(inputs[0]).toHaveAttribute('placeholder', 'Find this in the server console output.')
  await expect(
    page.getByRole('button', { name: 'Create Administrator Account', exact: true }),
  ).toBeVisible()

  return inputs
}

test.describe('first-run browser journey', () => {
  test.describe.configure({ mode: 'serial' })

  test.beforeAll(() => {
    if (
      !process.env.OWLCULUS_BASE_URL ||
      !process.env.OWLCULUS_SETUP_TOKEN ||
      !process.env.OWLCULUS_SERVER_KIND ||
      !process.env.OWLCULUS_VIEWPORT
    ) {
      throw new Error(
        'OWLCULUS_BASE_URL, OWLCULUS_SETUP_TOKEN, OWLCULUS_SERVER_KIND, and OWLCULUS_VIEWPORT must be provided by the ephemeral-stack runner',
      )
    }
  })

  test('shows only neutral loading content before routing login to setup', async ({ page }) => {
    const { assertSafeTraffic } = observeBrowserRuntime(page)
    let releaseStatusRequest
    let markStatusRequested
    const statusRequestWasMade = new Promise((resolve) => {
      markStatusRequested = resolve
    })
    const statusRequestMayContinue = new Promise((resolve) => {
      releaseStatusRequest = resolve
    })

    await page.route(
      '**/api/auth/setup-status',
      async (route) => {
        markStatusRequested()
        await statusRequestMayContinue
        await route.continue()
      },
      { times: 1 },
    )

    await page.goto('/login', { waitUntil: 'domcontentloaded' })
    await statusRequestWasMade

    await expect(page.getByRole('status')).toHaveText('Loading...')
    await expect(page.getByRole('button', { name: 'Sign in' })).toHaveCount(0)
    await expect(page.getByText('Case Management')).toHaveCount(0)

    releaseStatusRequest()
    await expectSetupForm(page)

    await page.goto('/cases')
    await expectSetupForm(page)
    assertSafeTraffic()
  })

  test('creates the first administrator and verifies the credentials through login', async ({
    page,
  }) => {
    const { assertSafeTraffic } = observeBrowserRuntime(page, {
      expectedConsoleErrors: [
        {
          message:
            /Failed to load resource: the server responded with a status of 403 \(Forbidden\)/,
          pathname: '/api/users/',
        },
      ],
    })
    let administratorRequests = 0
    page.on('request', (request) => {
      if (requestMatches(request, 'POST', '/api/users/')) {
        administratorRequests += 1
      }
    })

    await page.goto('/cases')
    const [setupToken, username, email, password, confirmPassword] = await expectSetupForm(page)

    await setupToken.fill('invalid-token')
    await username.fill(administrator.username)
    await email.fill(administrator.email)
    await password.fill(administrator.password)
    await confirmPassword.fill('different-password')
    await page.getByRole('button', { name: 'Create Administrator Account' }).click()
    await expect(visibleAlert(page, 'Passwords do not match')).toHaveText('Passwords do not match')
    expect(administratorRequests).toBe(0)

    await password.fill('short')
    await confirmPassword.fill('short')
    await page.getByRole('button', { name: 'Create Administrator Account' }).click()
    await expect(visibleAlert(page, 'Password must be at least 10 characters')).toHaveText(
      'Password must be at least 10 characters',
    )
    expect(administratorRequests).toBe(0)

    await password.fill(administrator.password)
    await confirmPassword.fill(administrator.password)

    let releaseAdministratorRequest
    let markAdministratorRequestStarted
    const administratorRequestStarted = new Promise((resolve) => {
      markAdministratorRequestStarted = resolve
    })
    const administratorRequestMayContinue = new Promise((resolve) => {
      releaseAdministratorRequest = resolve
    })

    await page.route(
      '**/api/users/',
      async (route) => {
        markAdministratorRequestStarted()
        await administratorRequestMayContinue
        await route.continue()
      },
      { times: 1 },
    )

    await page.getByRole('button', { name: 'Create Administrator Account' }).click()
    await administratorRequestStarted

    try {
      for (const input of [setupToken, username, email, password, confirmPassword]) {
        await expect(input).toBeDisabled()
      }
      await expect(page.getByRole('button', { name: 'Creating account...' })).toBeDisabled()
    } finally {
      releaseAdministratorRequest()
    }

    await expect(visibleAlert(page, 'Invalid setup token')).toHaveText('Invalid setup token')
    await expect(username).toHaveValue(administrator.username)
    await expect(page.getByRole('button', { name: 'Create Administrator Account' })).toBeEnabled()

    await setupToken.fill(process.env.OWLCULUS_SETUP_TOKEN)
    const administratorCreated = page.waitForResponse((response) =>
      requestMatches(response.request(), 'POST', '/api/users/'),
    )
    await page.getByRole('button', { name: 'Create Administrator Account' }).click()
    expect((await administratorCreated).status()).toBe(201)
    await expect(page).toHaveURL(/\/login$/)
    expect(await page.evaluate(() => localStorage.getItem('access_token'))).toBeNull()

    await page.getByLabel('Username', { exact: true }).fill(administrator.username)
    await page.getByLabel('Password', { exact: true }).fill(administrator.password)
    const loggedIn = page.waitForResponse((response) =>
      requestMatches(response.request(), 'POST', '/api/auth/login'),
    )
    const currentUserLoaded = page.waitForResponse((response) =>
      requestMatches(response.request(), 'GET', '/api/users/me'),
    )
    await page.getByRole('button', { name: 'Sign in' }).click()
    expect((await loggedIn).status()).toBe(200)
    expect((await currentUserLoaded).status()).toBe(200)
    expect(await page.evaluate(() => Boolean(localStorage.getItem('access_token')))).toBe(true)
    await expect(page).toHaveURL(/\/cases$/)
    await expect(page.getByText('Case Management')).toBeVisible()

    await page.goto('/setup')
    await expect(page).toHaveURL(/\/cases$/)
    await expect(page.getByText('Case Management')).toBeVisible()

    await page.evaluate(() => {
      localStorage.clear()
      sessionStorage.clear()
    })
    await page.goto('/setup')
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible()

    expect(administratorRequests).toBe(2)
    assertSafeTraffic()
  })

  test('smokes authenticated routes and representative interface behavior', async ({ page }) => {
    test.setTimeout(90_000)
    const { assertSafeTraffic, verifyViteHotReload } = observeBrowserRuntime(page)
    expect(page.viewportSize()).toEqual(browserViewports[process.env.OWLCULUS_VIEWPORT])
    await logIn(page)
    await verifyViteHotReload()

    await page.getByRole('button', { name: 'Dark Mode' }).click()
    await expect(page.getByRole('button', { name: 'Light Mode' })).toBeVisible()
    expect(await page.evaluate(() => localStorage.getItem('color-scheme'))).toBe('dark')
    await page.getByRole('button', { name: 'Light Mode' }).click()
    await expect(page.getByRole('button', { name: 'Dark Mode' })).toBeVisible()
    expect(await page.evaluate(() => localStorage.getItem('color-scheme'))).toBe('light')

    await page.getByRole('link', { name: 'Clients', exact: true }).click()
    await expect(page).toHaveURL(/\/clients$/, { timeout: 15_000 })
    await expect(page.getByText('Client Management')).toBeVisible({ timeout: 15_000 })

    await page.getByRole('button', { name: 'Add Client' }).click()
    const clientDialog = page.getByRole('dialog').filter({ hasText: 'New Client' })
    await expect(clientDialog).toBeVisible()
    await expect(clientDialog.getByText('New Client', { exact: true })).toBeVisible()
    await clientDialog.getByLabel('Name', { exact: true }).fill('Migration Safety Client')
    await clientDialog.getByLabel('Email', { exact: true }).fill('safety-client@example.org')
    await clientDialog.getByLabel('Phone', { exact: true }).fill('+1 555 0100')
    await clientDialog.getByLabel('Address', { exact: true }).fill('1 Regression Way')
    await clientDialog.getByRole('button', { name: 'Create Client' }).click()

    await expect(
      page.getByText('Client "Migration Safety Client" created successfully'),
    ).toBeVisible()
    const clientRow = page.getByRole('row').filter({ hasText: 'Migration Safety Client' })
    await expect(clientRow).toContainText('safety-client@example.org')

    const routeSmokeChecks = [
      {
        linkName: 'Cases',
        expectedUrl: /\/cases$/,
        landmark: page.getByText('Case Management', { exact: true }),
        verifyOperable: async () => {
          await exerciseTextInput(page.getByLabel('Search cases...', { exact: true }))
          await exerciseCaseAndEntityWorkflow(page)
        },
      },
      {
        linkName: 'Tasks',
        expectedUrl: /\/tasks$/,
        landmark: page.getByText('Task Management', { exact: true }),
        verifyOperable: async () => {
          await exerciseTextInput(page.getByLabel('Search tasks...', { exact: true }))
        },
      },
      {
        linkName: 'Hunts',
        expectedUrl: /\/hunts$/,
        landmark: page.getByText('Hunt Management', { exact: true }),
        verifyOperable: async () => {
          const historyTab = page.getByRole('tab', { name: 'Execution History', exact: true })
          await historyTab.click()
          await expect(historyTab).toHaveAttribute('aria-selected', 'true')
          await page.getByRole('tab', { name: /^Available Hunts/ }).click()
        },
      },
      {
        linkName: 'Admin',
        expectedUrl: /\/admin$/,
        landmark: page.getByRole('tab', { name: 'Users', exact: true }),
        verifyOperable: async () => {
          const invitesTab = page.getByRole('tab', { name: 'Invites', exact: true })
          await invitesTab.click()
          await expect(invitesTab).toHaveAttribute('aria-selected', 'true')
          await page.getByRole('tab', { name: 'Users', exact: true }).click()
        },
      },
    ]

    for (const { linkName, expectedUrl, landmark, verifyOperable } of routeSmokeChecks) {
      await page.getByRole('link', { name: linkName, exact: true }).click()
      await expect(page).toHaveURL(expectedUrl, { timeout: 15_000 })
      await expect(landmark).toBeVisible({ timeout: 15_000 })
      await verifyOperable()
    }

    await page.goto('/settings')
    await expect(page).toHaveURL(/\/settings$/, { timeout: 15_000 })
    await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible({
      timeout: 15_000,
    })
    const settingsFields = ['Current Password', 'New Password', 'Confirm New Password'].map(
      (label) => page.getByLabel(label, { exact: true }),
    )
    for (const field of settingsFields) {
      await expect(field).toBeVisible()
      await expect(field).toBeEnabled()
    }
    await exerciseTextInput(settingsFields[0])

    assertSafeTraffic()
  })
})
