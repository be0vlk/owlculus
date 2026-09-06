import { Buffer } from 'node:buffer'
import { readFile } from 'node:fs/promises'
import { execFileSync } from 'node:child_process'
import { expect, test } from '@playwright/test'
import { adminHeaders, bootstrap, investigatorCases, json, loginUi } from './support/workflow'

// The runner owns all fixture resources and removes its volumes even on failure.
test.use({ trace: 'retain-on-failure', screenshot: 'only-on-failure' })
test.setTimeout(60_000)
test.beforeAll(async ({ request }) => bootstrap(request))
test.beforeEach(async ({ page }) => page.setDefaultTimeout(15_000))

async function workspace(page, request) {
  const fixture = await investigatorCases(request)
  await loginUi(page, fixture.credentials)
  return { ...fixture, original: fixture.cases[0], other: fixture.cases[1] }
}

async function download(page, control, filename) {
  const [artifact] = await Promise.all([page.waitForEvent('download'), control.click()])
  expect(await artifact.failure()).toBeNull()
  const path = test.info().outputPath(filename)
  await artifact.saveAs(path)
  await test.info().attach(filename, { path })
  return path
}

async function rejectRequest(page, method, path) {
  const handler = (route) =>
    route.request().method() === method
      ? route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Controlled integrity transport failure' }),
        })
      : route.fallback()
  await page.route(`**${path}`, handler)
  return () => page.unroute(`**${path}`, handler)
}

async function seedEvidence(request, headers, record, name) {
  const folder = await json(
    await request.post('/api/evidence/folders', {
      headers,
      data: { case_id: record.id, title: `Folder-${name}` },
    }),
  )
  const bytes = Buffer.from(`Original bytes — ${name}\n\0end`)
  const evidence = await json(
    await request.post(`/api/evidence/?case_id=${record.id}&title=${name}&category=Documents`, {
      headers,
      multipart: {
        parent_folder_id: String(folder.id),
        folder_path: folder.folder_path,
        files: { name: `${name}.txt`, mimeType: 'text/plain', buffer: bytes },
      },
    }),
  )
  return { folder, file: evidence.created[0], bytes }
}

async function openEvidence(page, record, folder) {
  await page.goto(`/case/${record.id}?tab=evidence`)
  await page.getByText(folder.title, { exact: true }).click()
}

test('organized Evidence preserves identity and original downloaded bytes', async ({
  page,
  request,
}) => {
  const { headers, original } = await workspace(page, request)
  await page.goto(`/case/${original.id}?tab=evidence`)
  await page.getByRole('button', { name: 'Create Folder', exact: true }).click()
  const folderDialog = page.getByRole('dialog', { name: 'Create New Folder', exact: true })
  await folderDialog.getByLabel('Folder Name', { exact: true }).fill('Archive')
  await folderDialog.getByRole('button', { name: 'Create Folder', exact: true }).click()
  await expect(folderDialog).toBeHidden()
  await page.getByRole('button', { name: 'Actions for Archive', exact: true }).click()
  await page.getByText('Upload Files', { exact: true }).click()
  const upload = page.getByRole('dialog', { name: 'Upload Evidence', exact: true })
  const bytes = Buffer.from('Unmodified investigation bytes\n\0東京')
  await upload
    .locator('input[type=file]')
    .setInputFiles({ name: 'original.txt', mimeType: 'text/plain', buffer: bytes })
  await upload.getByRole('button', { name: 'Upload', exact: true }).click()
  await expect(upload).toBeHidden()
  await page.getByText('Archive', { exact: true }).click()
  const before = (
    await json(await request.get(`/api/evidence/case/${original.id}`, { headers }))
  ).find((item) => item.title === 'original.txt')
  expect(before).toBeTruthy()
  await page.getByRole('button', { name: 'Actions for original.txt', exact: true }).click()
  await page.getByText('Rename', { exact: true }).click()
  const rename = page.getByRole('dialog', { name: 'Rename evidence', exact: true })
  await rename.getByLabel('Name', { exact: true }).fill('organized.txt')
  await rename.getByRole('button', { name: 'Rename', exact: true }).click()
  await expect(rename).toBeHidden()
  await page.getByRole('button', { name: 'Create Folder', exact: true }).click()
  await folderDialog.getByLabel('Folder Name', { exact: true }).fill('Final')
  await folderDialog.getByRole('button', { name: 'Create Folder', exact: true }).click()
  await expect(folderDialog).toBeHidden()
  await page.getByText('organized.txt', { exact: true }).hover()
  await page.mouse.down()
  await page.getByText('Final', { exact: true }).hover()
  await page.getByText('Final', { exact: true }).hover()
  await page.mouse.up()
  await expect(
    page.getByRole('status').filter({ hasText: 'Evidence moved to Final' }),
  ).toBeVisible()
  await page.reload()
  await page.getByText('Final', { exact: true }).click()
  const control = page.getByRole('button', { name: 'Download organized.txt', exact: true })
  await expect(control).toBeVisible()
  const records = await json(await request.get(`/api/evidence/case/${original.id}`, { headers }))
  const folder = records.find((item) => item.title === 'Final')
  expect
    .soft(await json(await request.get(`/api/evidence/${before.id}`, { headers })))
    .toMatchObject({
      id: before.id,
      case_id: original.id,
      title: 'organized.txt',
      parent_folder_id: folder.id,
      folder_path: folder.folder_path,
    })
  expect(await readFile(await download(page, control, 'organized.txt'))).toEqual(bytes)
})

for (const kind of ['Case', 'Entity']) {
  for (const fails of [false, true]) {
    test(`${kind} notes ${fails ? 'retain failed draft and retry' : 'persist supported formatting after reopening'}`, async ({
      page,
      request,
    }) => {
      const { headers, original, marker } = await workspace(page, request)
      let path = `/api/cases/${original.id}`
      let entity
      if (kind === 'Entity') {
        entity = await json(
          await request.post(`${path}/entities`, {
            headers,
            data: {
              entity_type: 'person',
              data: { first_name: 'Notes', last_name: marker, notes: '<p>Acknowledged notes</p>' },
            },
          }),
        )
        path += `/entities/${entity.id}`
      } else {
        await json(
          await request.put(path, { headers, data: { notes: '<p>Acknowledged notes</p>' } }),
        )
      }
      const open = async () => {
        await page.goto(`/case/${original.id}?tab=${kind === 'Case' ? 'notes' : 'entities'}`)
        if (entity) {
          await page.getByRole('button', { name: `View Notes ${marker}`, exact: true }).click()
          await page
            .getByRole('dialog', { name: `Notes ${marker}`, exact: true })
            .getByRole('tab', { name: 'Notes', exact: true })
            .click()
          await page.getByRole('button', { name: 'Edit Entity', exact: true }).click()
        } else await page.getByRole('button', { name: 'Edit Notes', exact: true }).click()
      }
      await open()
      const editor = page.getByRole('textbox', { name: `${kind} notes`, exact: true })
      await expect(editor).toHaveText('Acknowledged notes')
      const restore = fails ? await rejectRequest(page, 'PUT', path) : null
      const draft = `${kind} formatted findings ${marker}`
      await editor.fill(draft)
      await editor.press('ControlOrMeta+a')
      await page.getByRole('button', { name: 'Bold (Ctrl+B)', exact: true }).click()
      const save = page.getByRole('button', { name: entity ? 'Save Changes' : 'Save', exact: true })
      await save.click()
      if (fails) {
        await expect(page.getByRole('alert').filter({ hasText: 'Failed to save' })).toBeVisible()
        await expect(editor).toHaveText(draft)
        await expect(editor.locator('strong')).toHaveText(draft)
        await expect(page.getByText(/Last saved:|Notes saved successfully/)).toHaveCount(0)
        const acknowledged = await json(await request.get(path, { headers }))
        expect(entity ? acknowledged.data.notes : acknowledged.notes).toBe(
          '<p>Acknowledged notes</p>',
        )
        await restore()
        await save.click()
      }
      await expect
        .poll(async () => {
          const record = await json(await request.get(path, { headers }))
          return entity ? record.data.notes : record.notes
        })
        .toContain(`<strong>${draft}</strong>`)
      await page.reload()
      await open()
      await expect(editor).toHaveText(draft)
      await expect(editor.locator('strong')).toHaveText(draft)
      const persisted = await json(await request.get(path, { headers }))
      expect(persisted.id).toBe(entity ? entity.id : original.id)
      if (entity) expect(persisted.case_id).toBe(original.id)
    })
  }
}

for (const kind of ['Evidence download', 'Case export']) {
  test(`${kind} reports transport failure and retries a valid artifact`, async ({
    page,
    request,
  }) => {
    const { headers, original, marker } = await workspace(page, request)
    const seeded = await seedEvidence(request, headers, original, marker)
    await openEvidence(page, original, seeded.folder)
    const isExport = kind === 'Case export'
    const path = isExport
      ? `/api/cases/${original.id}/export`
      : `/api/evidence/${seeded.file.id}/download`
    const control = page.getByRole('button', {
      name: isExport ? 'Export' : `Download ${seeded.file.title}`,
      exact: true,
    })
    const artifacts = []
    page.on('download', (artifact) => artifacts.push(artifact))
    const restore = await rejectRequest(page, 'GET', path)
    const failed = page.waitForResponse(
      (response) => new URL(response.url()).pathname === path && response.status() === 503,
    )
    await control.click()
    await failed
    // Soft assertion preserves the real retry evidence even for a missing error UI.
    await expect
      .soft(page.getByText(isExport ? 'Failed to export case' : /Failed to download evidence/i))
      .toBeVisible()
    expect(artifacts).toHaveLength(0)
    await expect(page.getByText('Case exported successfully', { exact: true })).toHaveCount(0)
    await restore()
    const artifact = await download(page, control, isExport ? 'retry.zip' : 'retry.txt')
    if (isExport) {
      const members = await inspectArchive(artifact)
      expect(
        Buffer.from(
          members[`${original.case_number}/evidence/${seeded.folder.title}/${seeded.file.title}`],
          'base64',
        ),
      ).toEqual(seeded.bytes)
    } else expect(await readFile(artifact)).toEqual(seeded.bytes)
    expect(artifacts).toHaveLength(1)
  })
}

async function inspectArchive(path) {
  // Python's standard ZIP reader validates CRCs without adding an archive dependency.
  const members = JSON.parse(
    execFileSync(
      'uv',
      [
        'run',
        '--no-project',
        'python',
        '-c',
        'import sys,zipfile,json,base64; z=zipfile.ZipFile(sys.argv[1]); print(json.dumps({n:base64.b64encode(z.read(n)).decode() for n in z.namelist()}))',
        path,
      ],
      { encoding: 'utf8' },
    ),
  )
  await test.info().attach('archive-members.json', {
    body: JSON.stringify(members, null, 2),
    contentType: 'application/json',
  })
  return members
}

test('Case export contains intended investigation records and excludes the other Case', async ({
  page,
  request,
}) => {
  const { headers, original, other, marker } = await workspace(page, request)
  const fixtures = []
  for (const record of [original, other]) {
    const name = `${record.id}-${marker}`
    const notes = `<p><strong>Notes ${name}</strong></p>`
    await json(
      await request.put(`/api/cases/${record.id}`, {
        headers,
        data: { notes },
      }),
    )
    const entity = await json(
      await request.post(`/api/cases/${record.id}/entities`, {
        headers,
        data: { entity_type: 'person', data: { first_name: name, notes: `<p>Entity ${name}</p>` } },
      }),
    )
    const task = await json(
      await request.post('/api/tasks/', {
        headers: await adminHeaders(request),
        data: {
          case_id: record.id,
          title: `Task ${name}`,
          description: `Task description ${name}`,
        },
      }),
    )
    fixtures.push({
      ...(await seedEvidence(request, headers, record, name)),
      entity,
      task,
      notes,
      name,
    })
  }
  await page.goto(`/case/${original.id}?tab=notes`)
  const members = await inspectArchive(
    await download(page, page.getByRole('button', { name: 'Export', exact: true }), 'case.zip'),
  )
  const text = (path) =>
    Buffer.from(members[`${original.case_number}/${path}`], 'base64').toString('utf8')
  const [included, excluded] = fixtures
  expect(JSON.parse(text('case.json'))).toMatchObject({
    id: original.id,
    title: original.title,
    case_number: original.case_number,
    status: original.status,
    client: { id: original.client_id },
  })
  expect(text('notes.html')).toBe(included.notes)
  expect(JSON.parse(text('entities/entities.json'))).toEqual([
    expect.objectContaining({
      id: included.entity.id,
      case_id: original.id,
      data: expect.objectContaining({
        first_name: included.name,
        notes: `<p>Entity ${included.name}</p>`,
      }),
    }),
  ])
  expect(JSON.parse(text('tasks/tasks.json'))).toEqual([
    expect.objectContaining({
      id: included.task.id,
      title: included.task.title,
      description: included.task.description,
    }),
  ])
  expect(JSON.parse(text('evidence/manifest.json'))).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        id: included.file.id,
        title: included.file.title,
        folder_path: included.folder.folder_path,
        exported: true,
      }),
    ]),
  )
  expect(
    Buffer.from(
      members[`${original.case_number}/evidence/${included.folder.title}/${included.file.title}`],
      'base64',
    ),
  ).toEqual(included.bytes)
  for (const [name, content] of Object.entries(members)) {
    expect(name.startsWith(`${original.case_number}/`)).toBe(true)
    expect(name).not.toContain(excluded.name)
    expect(Buffer.from(content, 'base64').includes(Buffer.from(excluded.name))).toBe(false)
  }
})
