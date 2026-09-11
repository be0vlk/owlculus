import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount, DOMWrapper } from '@vue/test-utils'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import UploadEvidenceModal from '../UploadEvidenceModal.vue'
import { evidenceService } from '@/services/evidence'

vi.mock('@/services/evidence', () => ({
  evidenceService: { createEvidence: vi.fn(), getFolderTree: vi.fn().mockResolvedValue([]) },
}))
let wrapper

afterEach(() => {
  wrapper?.unmount()
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
})

beforeEach(() => {
  vi.stubGlobal('visualViewport', new EventTarget())
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
})

async function mountModal() {
  wrapper = mount(UploadEvidenceModal, {
    props: { show: true, caseId: 7, targetFolder: { id: 1, title: 'Documents' } },
    attachTo: document.body,
    global: { plugins: [createVuetify({ components, directives, theme: false })] },
  })
  await flushPromises()
  return new DOMWrapper(document.querySelector('[role="dialog"][aria-label="Upload Evidence"]'))
}

it('reports partial upload failure and retries only the remaining files', async () => {
  const created = { id: 2, title: 'statement.txt' }
  evidenceService.createEvidence.mockResolvedValueOnce({
    created: [created],
    failed: [{ filename: 'photo.png', error: 'Storage unavailable' }],
  })
  const dialog = await mountModal()
  const input = dialog.get('input[type="file"]')
  const photo = new File(['photo'], 'photo.png', { type: 'image/png' })
  Object.defineProperty(input.element, 'files', {
    value: [new File(['statement'], 'statement.txt'), photo],
  })
  await input.trigger('change')
  const upload = dialog.findAll('button').find((button) => button.text().trim() === 'Upload')
  await upload.trigger('click')
  await flushPromises()
  expect(dialog.text()).toContain('photo.png: Storage unavailable')
  expect(wrapper.emitted('uploaded')).toEqual([[[created]]])
  expect(wrapper.emitted('close')).toBeUndefined()
  evidenceService.createEvidence.mockResolvedValueOnce({
    created: [{ id: 3, title: 'photo.png' }],
    failed: [],
  })
  await upload.trigger('click')
  await flushPromises()
  expect(evidenceService.createEvidence.mock.calls[1][0].files).toEqual([photo])
  expect(wrapper.emitted('close')).toHaveLength(1)
})

it('rejects duplicate filenames so failed uploads can be retried unambiguously', async () => {
  const dialog = await mountModal()
  const input = dialog.get('input[type="file"]')
  Object.defineProperty(input.element, 'files', {
    value: [new File(['first'], 'statement.txt'), new File(['second'], 'statement.txt')],
  })
  await input.trigger('change')
  expect(dialog.text()).toContain('Files must have unique names')
  expect(
    dialog
      .findAll('button')
      .find((button) => button.text().trim() === 'Upload')
      .attributes('disabled'),
  ).toBeDefined()
})

it('reports aggregate rejection without claiming Evidence was saved', async () => {
  evidenceService.createEvidence.mockRejectedValueOnce({ response: { status: 413 } })
  const dialog = await mountModal()
  const input = dialog.get('input[type="file"]')
  const photo = new File(['photo'], 'photo.png', { type: 'image/png' })
  Object.defineProperty(input.element, 'files', {
    value: [new File(['statement'], 'statement.txt'), photo],
  })
  await input.trigger('change')
  const upload = dialog.findAll('button').find((button) => button.text().trim() === 'Upload')
  await upload.trigger('click')
  await flushPromises()
  expect(dialog.text()).toContain('Upload too large. No Evidence was saved.')
  expect(wrapper.emitted('uploaded')).toBeUndefined()
  expect(wrapper.emitted('close')).toBeUndefined()
  expect(dialog.text()).toContain('statement.txt')
  expect(dialog.text()).toContain('photo.png')
})
