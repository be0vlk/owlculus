import process from 'node:process'
import { expect, test } from '@playwright/test'

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

function observeSameOriginTraffic(page) {
  const browserOrigin = new URL(process.env.OWLCULUS_BASE_URL).origin
  const preflightRequests = []
  const unsafeRequests = []
  const failedRequests = []
  const browserErrors = []
  const uncaughtErrors = []
  const hotReloadConnections = []

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
    if (process.env.OWLCULUS_SERVER_KIND === 'vite') {
      hotReloadConnections.push(websocket.url())
    }
    if (websocketUrl.port === '8000' || websocketOrigin(websocket.url()) !== browserOrigin) {
      unsafeRequests.push(websocket.url())
    }
    websocket.on('socketerror', (error) => {
      failedRequests.push(`${websocket.url()}: ${error}`)
    })
  })

  page.on('requestfailed', (request) => {
    failedRequests.push(`${request.url()}: ${request.failure()?.errorText || 'unknown failure'}`)
  })

  page.on('console', (message) => {
    if (
      message.type() === 'error' &&
      /cors|cross-origin|mixed content|preflight/i.test(message.text())
    ) {
      browserErrors.push(message.text())
    }
  })

  page.on('pageerror', (error) => {
    uncaughtErrors.push(error.message)
  })

  return () => {
    expect(preflightRequests, 'browser should not make CORS preflight requests').toEqual([])
    expect(unsafeRequests, 'browser requests should stay on the page origin').toEqual([])
    expect(failedRequests, 'browser requests should not fail').toEqual([])
    expect(browserErrors, 'browser console should have no origin or mixed-content errors').toEqual(
      [],
    )
    expect(uncaughtErrors, 'browser should have no uncaught exceptions').toEqual([])
    if (process.env.OWLCULUS_SERVER_KIND === 'vite') {
      expect(
        hotReloadConnections,
        'the development server should expose its hot-reload channel',
      ).not.toEqual([])
    }
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
    const assertSafeTraffic = observeSameOriginTraffic(page)
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
    const assertSafeTraffic = observeSameOriginTraffic(page)
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
    test.setTimeout(60_000)
    const assertSafeTraffic = observeSameOriginTraffic(page)
    const viewportWidths = { desktop: 1440, narrow: 390 }
    const expectedViewportWidth = viewportWidths[process.env.OWLCULUS_VIEWPORT]
    expect(page.viewportSize()?.width).toBe(expectedViewportWidth)
    await logIn(page)

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
      ['Cases', /\/cases$/, page.getByText('Case Management', { exact: true })],
      ['Tasks', /\/tasks$/, page.getByText('Task Management', { exact: true })],
      ['Hunts', /\/hunts$/, page.getByText('Hunt Management', { exact: true })],
      ['Admin', /\/admin$/, page.getByRole('tab', { name: 'Users', exact: true })],
    ]

    for (const [linkName, expectedUrl, landmark] of routeSmokeChecks) {
      await page.getByRole('link', { name: linkName, exact: true }).click()
      await expect(page).toHaveURL(expectedUrl, { timeout: 15_000 })
      await expect(landmark).toBeVisible({ timeout: 15_000 })
    }

    await page.goto('/settings')
    await expect(page).toHaveURL(/\/settings$/, { timeout: 15_000 })
    await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible({
      timeout: 15_000,
    })

    assertSafeTraffic()
  })
})
