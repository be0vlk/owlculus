import process from 'node:process'
import { Buffer } from 'node:buffer'
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

async function captureReview(page, name) {
  const path = test.info().outputPath(`${name}.png`)
  // Full-page Chromium captures can briefly resize the viewport to 1px, starting
  // Vuetify scroll animations against geometry that disappears after capture.
  await page.screenshot({ path, animations: 'disabled' })
  await test.info().attach(name, { path, contentType: 'image/png' })
}

async function captureOperations(page, surface) {
  for (const theme of ['light', 'dark']) {
    if (theme === 'dark') await page.getByRole('button', { name: 'Dark Mode', exact: true }).click()
    await captureReview(page, `${surface}-${theme}`)
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true)
  }
  await page.getByRole('button', { name: 'Light Mode', exact: true }).click()
}

async function exerciseTasks(page) {
  await page.getByRole('button', { name: 'New Task', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Create Task', exact: true })
  await expect(dialog.getByLabel('Case', { exact: true })).toHaveCount(0)
  await dialog.getByLabel('Title', { exact: true }).fill('Migration review')
  await dialog.getByLabel('Description', { exact: true }).fill('Review migration behavior')
  await dialog.getByLabel('Title', { exact: true }).press('Enter')
  await expect(dialog).toBeHidden()
  await page.getByText('All Tasks', { exact: true }).click()
  const row = page.getByRole('row').filter({ hasText: 'Migration review' })
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: 'Assign Migration review', exact: true }).click()
  const assign = page.getByRole('dialog', { name: 'Assign Task', exact: true })
  await assign.getByLabel('Assign To', { exact: true }).press('ArrowDown')
  await page.getByRole('option', { name: administrator.username, exact: true }).click()
  await assign.getByRole('button', { name: 'Assign', exact: true }).click()
  await expect(assign).toBeHidden()
  await expect(page.getByText('Task assigned successfully', { exact: true })).toBeVisible()
  await captureOperations(page, 'tasks')
  await row.getByRole('link', { name: 'Migration review', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'Task: Migration review', exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Edit Task', exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'Edit Task', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
}

async function exerciseAdministration(page) {
  await page.getByRole('button', { name: 'Add User', exact: true }).click()
  const user = page.getByRole('dialog', { name: 'Add New User', exact: true })
  await user.getByLabel('Username', { exact: true }).fill('migration_user')
  await user.getByLabel('Email Address', { exact: true }).fill('migration-user@example.org')
  await user.getByLabel('Password', { exact: true }).fill('MigrationUser123!')
  await user.getByLabel('Password', { exact: true }).press('Enter')
  await expect(user).toBeHidden()
  await expect(page.getByRole('row').filter({ hasText: 'migration_user' })).toBeVisible()
  await page.getByRole('button', { name: 'Delete migration_user', exact: true }).click()
  const confirmation = page.getByRole('dialog', { name: 'Confirm Deletion', exact: true })
  await expect(confirmation).toContainText('This action cannot be undone.')
  await confirmation.getByRole('button', { name: 'Cancel', exact: true }).click()

  await page.getByRole('tab', { name: 'Invites', exact: true }).click()
  await page.getByRole('button', { name: 'Generate Invite', exact: true }).first().click()
  const invite = page.getByRole('dialog', { name: 'Generate Invite', exact: true })
  await invite.getByRole('button', { name: 'Generate Invite', exact: true }).click()
  await expect(invite).toBeHidden()
  await expect(page.getByRole('button', { name: 'Copy invite link', exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Add API Key', exact: true }).click()
  const apiKey = page.getByRole('dialog', { name: 'Add API Key', exact: true })
  await apiKey.getByLabel('Provider', { exact: true }).press('ArrowDown')
  await page.getByRole('option', { name: 'Shodan', exact: true }).click()
  await apiKey.getByLabel('API Key', { exact: true }).fill('disposable-migration-key')
  await apiKey.getByRole('button', { name: 'Add API Key', exact: true }).click()
  await expect(apiKey).toBeHidden()
  await expect(page.getByText('API key added successfully!', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Add Template', exact: true }).click()
  const template = page.getByRole('dialog', { name: 'Add Task Template', exact: true })
  await template.getByLabel('Template Name', { exact: true }).fill('migration_review')
  await template.getByLabel('Display Name', { exact: true }).fill('Migration Review')
  await template.getByLabel('Description', { exact: true }).fill('Review migration checks')
  await template.getByLabel('Category', { exact: true }).fill('Review')
  await template.getByLabel('Display Name', { exact: true }).press('Enter')
  await expect(template).toBeHidden()
  await expect(page.getByRole('row').filter({ hasText: 'Migration Review' })).toBeVisible()
  await page.getByRole('button', { name: 'Edit Migration Review', exact: true }).click()
  const edit = page.getByRole('dialog', { name: 'Edit Task Template', exact: true })
  await expect(edit.getByLabel('Template Name', { exact: true })).toBeDisabled()
  await edit.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'Case Number Configuration', exact: true }),
  ).toBeVisible()
  await page.getByLabel('Case Number Format', { exact: true }).press('ArrowDown')
  await page
    .getByRole('option', { name: 'Prefix + Monthly Reset (PREFIX-YYMM-NN)', exact: true })
    .click()
  const prefix = page.getByLabel('Prefix (2-8 letters/numbers)', { exact: true })
  await prefix.fill('X')
  await expect(page.getByRole('button', { name: 'Save Configuration', exact: true })).toBeDisabled()
  await prefix.fill('MIG')
  await page.getByRole('button', { name: 'Save Configuration', exact: true }).click()
  await expect(page.getByText('Configuration saved successfully!', { exact: true })).toBeVisible()
  await captureOperations(page, 'administration')
}

async function uploadEvidence(page, folderName, file) {
  await page.getByRole('button', { name: `Actions for ${folderName}`, exact: true }).click()
  await page.getByText('Upload Files', { exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Upload Evidence', exact: true })
  await dialog.locator('input[type="file"]').setInputFiles(file)
  await dialog.getByRole('button', { name: 'Upload', exact: true }).click()
  await expect(dialog).toBeHidden()
}

async function exerciseEvidenceAndNotes(page) {
  const createFolder = page.getByRole('button', { name: 'Create Folder', exact: true })
  await createFolder.click()
  const folderDialog = page.getByRole('dialog', { name: 'Create New Folder', exact: true })
  await expect(folderDialog.getByLabel('Folder Name', { exact: true })).toBeFocused()
  await captureReview(page, 'evidence-folder-dialog-light')
  await page.keyboard.press('Shift+Tab')
  await expect(folderDialog.locator(':focus')).toHaveCount(1)
  await page.keyboard.press('Escape')
  await expect(folderDialog).toBeHidden()
  await expect(createFolder).toBeFocused()
  await createFolder.click()
  await folderDialog.getByLabel('Folder Name', { exact: true }).fill('Documents')
  await folderDialog.getByRole('button', { name: 'Create Folder', exact: true }).click()
  await expect(folderDialog).toBeHidden()
  await uploadEvidence(page, 'Documents', {
    name: 'statement.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('Witness statement for migration verification'),
  })
  await page.getByText('Documents', { exact: true }).click()
  const previewButton = page.getByRole('button', { name: 'Preview statement.txt', exact: true })
  await expect(previewButton).toBeVisible()
  await previewButton.click()
  const preview = page.getByRole('dialog', {
    name: 'Text File Content: statement.txt',
    exact: true,
  })
  await expect(preview).toContainText('Witness statement for migration verification')
  await page.keyboard.press('Escape')
  await expect(preview).toBeHidden()
  await expect(previewButton).toBeFocused()
  await uploadEvidence(page, 'Documents', 'public/owl_logo.png')
  await page.getByRole('button', { name: 'Actions for owl_logo.png', exact: true }).click()
  await page.getByText('Extract Metadata', { exact: true }).click()
  const metadata = page.getByRole('dialog', { name: 'File Metadata', exact: true })
  await expect(metadata.getByText('owl_logo.png', { exact: true })).toBeVisible()
  const category = metadata.getByRole('button', { name: /Metadata.*fields/i }).first()
  await category.click()
  await expect(category).toHaveAttribute('aria-expanded', 'true')
  await expect(metadata.getByText('File Modify Date', { exact: true })).toBeVisible()
  await captureReview(page, 'metadata-expanded-light')
  await metadata.getByRole('button', { name: 'Close', exact: true }).click()
  await page.getByRole('checkbox', { name: 'Select statement.txt', exact: true }).check()
  await expect(page.getByText('1 selected', { exact: true })).toBeVisible()
  await createFolder.click()
  await folderDialog.getByLabel('Folder Name', { exact: true }).fill('Archive')
  await folderDialog.getByRole('button', { name: 'Create Folder', exact: true }).click()
  await expect(folderDialog).toBeHidden()
  await expect(previewButton).toBeVisible()
  await page.getByText('statement.txt', { exact: true }).hover()
  await page.mouse.down()
  await page.getByText('Archive', { exact: true }).hover()
  // A second move delivers dragover consistently across browsers.
  await page.getByText('Archive', { exact: true }).hover()
  await captureReview(page, 'evidence-drag-target-light')
  await page.mouse.up()
  await expect(
    page.getByRole('status').filter({ hasText: 'Evidence moved to Archive' }),
  ).toBeVisible()
  await page.getByText('Archive', { exact: true }).click()
  await expect(previewButton).toBeVisible()
  await page
    .getByRole('button', { name: 'Delete statement.txt', exact: true })
    .click({ trial: true })
  await captureOperations(page, 'evidence')
  await page.getByRole('button', { name: 'Delete statement.txt', exact: true }).click()
  const deleteDialog = page.getByRole('dialog', { name: 'Confirm Delete', exact: true })
  await expect(deleteDialog).toContainText('statement.txt')
  await page.keyboard.press('Escape')
  await expect(deleteDialog).toBeHidden()

  await page.getByRole('tab', { name: 'Notes', exact: true }).click()
  await page.getByRole('button', { name: 'Edit Notes', exact: true }).click()
  const notes = page.getByRole('textbox', { name: 'Case notes', exact: true })
  await notes.fill('Investigation notes')
  await notes.press('ControlOrMeta+a')
  const bold = page.getByRole('button', { name: 'Bold (Ctrl+B)', exact: true })
  await bold.click()
  await expect(bold).toHaveAttribute('aria-pressed', 'true')
  const expand = page.getByRole('button', { name: 'Expand to fullscreen', exact: true })
  await expand.click()
  const fullscreen = page.getByRole('dialog', { name: 'Case Notes Editor', exact: true })
  await expect(fullscreen.getByRole('textbox', { name: 'Case notes', exact: true })).toContainText(
    'Investigation notes',
  )
  await fullscreen
    .getByRole('textbox', { name: 'Case notes', exact: true })
    .fill('Expanded investigation notes')
  await page.keyboard.press('Escape')
  await expect(fullscreen).toBeHidden()
  await expect(expand).toBeFocused()
  await expect(notes).toContainText('Expanded investigation notes')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Notes saved' })).toBeVisible()
  await page.getByRole('button', { name: 'Dark Mode', exact: true }).click()
  await expect(notes).toBeVisible()
  await expect(bold).toBeDisabled()
  await captureReview(page, 'evidence-notes-dark')
  await page.getByRole('button', { name: 'Light Mode', exact: true }).click()
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

  await expect(page).toHaveURL(/\/case\/\d+$/)
  await page.getByRole('button', { name: 'Dismiss', exact: true }).click()
  await page.getByRole('link', { name: 'Cases', exact: true }).click()
  const caseRow = page.getByRole('row').filter({ hasText: 'Migration Safety Case' })
  await expect(caseRow).toContainText('Migration Safety Client')
  await caseRow.getByRole('cell', { name: 'Migration Safety Case', exact: true }).click()
  await expect(page).toHaveURL(/\/case\/\d+$/)
  await expect(page.getByText('Case Information', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Manage Users', exact: true }).click()
  const members = page.getByRole('dialog', { name: 'Manage Case Users', exact: true })
  await members.getByLabel('Select User', { exact: true }).press('ArrowDown')
  await page.getByRole('option', { name: /e2e-admin@example.org/ }).click()
  await members.getByRole('button', { name: 'Add User', exact: true }).click()
  await expect(
    members.getByRole('button', { name: 'Remove e2e-admin@example.org from case', exact: true }),
  ).toBeVisible()
  await members.getByRole('button', { name: 'Done', exact: true }).click()

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

  await exerciseEvidenceAndNotes(page)

  const entitiesTab = page.getByRole('tab', { name: 'Entities', exact: true })
  await entitiesTab.click()
  await expect(entitiesTab).toHaveAttribute('aria-selected', 'true')
  await expect(page).not.toHaveURL(/[?&]tab=/)

  await expect(page.getByText('No Entities Found', { exact: true })).toBeVisible()
  await captureReview(page, 'entities-empty-light')
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
  // Saving also refreshes the table; wait for the replacement focus target.
  await expect(
    page.getByRole('button', { name: 'View Grace Lovelace', exact: true, includeHidden: true }),
  ).toBeVisible()
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
    if (
      message.type() === 'error' ||
      (message.type() === 'warning' && /Vue warn|Vuetify|deprecated/i.test(message.text()))
    ) {
      browserErrors.push({
        message: message.text(),
        sourceUrl: message.location().url,
        pageUrl: page.url(),
      })
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
    await captureReview(page, 'setup-loading')
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
    await captureReview(page, 'setup-validation-light')
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
    test.setTimeout(150_000)
    page.setDefaultTimeout(15_000)
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
    const clientDialog = page.getByRole('dialog', { name: 'New Client', exact: true })
    await expect(clientDialog).toBeVisible()
    await expect(clientDialog.getByText('New Client', { exact: true })).toBeVisible()
    await expect(clientDialog.getByLabel('Name', { exact: true })).toBeFocused()
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

    await captureOperations(page, 'clients')

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
          await exerciseTasks(page)
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
          await exerciseTextInput(page.getByLabel('Search hunts...', { exact: true }))
          await page.getByRole('button', { name: 'List view', exact: true }).click()
          await page.getByRole('button', { name: 'Grid view', exact: true }).click()
          await page.getByRole('button', { name: 'Execute Hunt', exact: true }).first().click()
          const huntDialog = page.getByRole('dialog', { name: 'Execute Hunt', exact: true })
          await expect(huntDialog.getByLabel('Select Case', { exact: true })).toHaveCount(0)
          await expect(
            huntDialog.getByRole('button', { name: 'Execute Hunt', exact: true }),
          ).toBeEnabled()
          await huntDialog.getByLabel('Domain *', { exact: true }).press('Enter')
          await expect(huntDialog.getByText('Domain is required', { exact: true })).toBeVisible()
          await huntDialog.getByRole('button', { name: 'Cancel', exact: true }).click()
          await captureOperations(page, 'hunts')
        },
      },
      {
        linkName: 'Admin',
        expectedUrl: /\/admin$/,
        landmark: page.getByRole('tab', { name: 'Users', exact: true }),
        verifyOperable: async () => {
          await exerciseAdministration(page)
        },
      },
    ]

    for (const { linkName, expectedUrl, landmark, verifyOperable } of routeSmokeChecks) {
      await page.getByRole('link', { name: linkName, exact: true }).click()
      await expect(page).toHaveURL(expectedUrl, { timeout: 15_000 })
      await expect(landmark).toBeVisible({ timeout: 15_000 })
      await verifyOperable()
    }

    await page.goto('/plugins')
    await expect(page.getByText('Plugin Management', { exact: true })).toBeVisible()
    await expect(
      page.getByRole('button', { name: 'Refresh plugins', exact: true }),
    ).toBeInViewport()
    await page.getByRole('button', { name: 'Configure Correlation Scan', exact: true }).click()
    await expect(page.getByLabel('Case to Scan', { exact: true })).toHaveCount(0)
    await page.getByRole('button', { name: 'Execute Plugin', exact: true }).click()
    const pluginDialog = page.getByRole('dialog', { name: 'Plugin results', exact: true })
    await expect(pluginDialog).toBeVisible()
    await expect(pluginDialog.getByText('Execution Parameters', { exact: true })).toBeVisible()
    await expect(pluginDialog.getByRole('button', { name: 'Export', exact: true })).toBeEnabled()
    await expect(
      pluginDialog.getByText('Correlation scan complete. No correlations found.', { exact: true }),
    ).toBeVisible()
    await captureReview(page, 'plugin-results-light')
    await pluginDialog.getByRole('button', { name: 'Close plugin results', exact: true }).click()
    await captureOperations(page, 'plugins')

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
    await settingsFields[0].fill(administrator.password)
    await settingsFields[1].fill('UpdatedPassword123!')
    await settingsFields[2].fill('MismatchPassword123!')
    await page.getByRole('button', { name: 'Update Password', exact: true }).click()
    await expect(visibleAlert(page, 'New passwords do not match')).toBeVisible()
    await settingsFields[2].fill('UpdatedPassword123!')
    await settingsFields[2].press('Enter')
    await expect(visibleAlert(page, 'Password updated successfully')).toBeVisible()
    await captureOperations(page, 'settings')

    assertSafeTraffic()
  })
})
