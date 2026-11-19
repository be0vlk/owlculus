import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import { evidenceService } from '@/services/evidence'
import EvidenceList from '../EvidenceList.vue'

vi.mock('@/services/evidence', () => ({
  evidenceService: { deleteEvidence: vi.fn(), updateEvidence: vi.fn() },
}))

const evidence = [
  { id: 1, title: 'Documents', is_folder: true },
  { id: 2, title: 'statement.txt', evidence_type: 'file', parent_folder_id: 1 },
]
let wrapper

afterEach(() => {
  wrapper?.unmount()
  document.body.innerHTML = ''
})

describe('Evidence tree', () => {
  it('preserves expanded folders across refreshes and exposes named file actions', async () => {
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    )
    wrapper = mount(EvidenceList, {
      props: { evidenceList: evidence, caseId: 7 },
      attachTo: document.body,
      global: { plugins: [createVuetify({ components, directives, theme: false })] },
    })
    await wrapper.get('[role="treeitem"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[aria-label="Preview statement.txt"]').isVisible()).toBe(true)
    await wrapper.setProps({
      evidenceList: [...evidence, { id: 3, title: 'Images', is_folder: true }],
    })
    await flushPromises()
    await wrapper.get('[aria-label="Preview statement.txt"]').trigger('click')
    expect(wrapper.emitted('view-content')[0][0]).toMatchObject({ id: 2 })
    await wrapper.get('[aria-label="Select statement.txt"]').setValue(true)
    expect(wrapper.text()).toContain('1 selected')
    await wrapper.get('[aria-label="Download statement.txt"]').trigger('click')
    expect(wrapper.emitted('download')[0][0]).toMatchObject({ id: 2 })
  })
  it('shows a failed move and restores the original evidence list', async () => {
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    )
    const items = [...evidence, { id: 3, title: 'Archive', is_folder: true }]
    wrapper = mount(EvidenceList, {
      props: { evidenceList: items, caseId: 7 },
      attachTo: document.body,
      global: { plugins: [createVuetify({ components, directives, theme: false })] },
    })
    const folder = wrapper
      .findAll('[role="treeitem"]')
      .find((item) => item.text().includes('Documents'))
    await folder.trigger('click')
    await flushPromises()
    const dataTransfer = { setData: vi.fn() }
    await wrapper.get('[draggable="true"]').trigger('dragstart', { dataTransfer })
    evidenceService.updateEvidence.mockRejectedValueOnce(new Error('Move unavailable'))
    const target = wrapper
      .findAll('.tree-item-title-wrapper')
      .find((item) => item.text() === 'Archive')
    await target.trigger('drop', { dataTransfer })
    await flushPromises()
    expect(evidenceService.updateEvidence).toHaveBeenCalledWith(2, { parentFolderId: 3 })
    const [[optimistic], [restored]] = wrapper.emitted('evidence-moved')
    expect(optimistic.find((item) => item.id === 2).parent_folder_id).toBe(3)
    expect(wrapper.get('[role="alert"]').text()).toContain('Move unavailable')
    expect(restored).toEqual(items)
  })
  it('confirms deletion and reports a failed delete', async () => {
    vi.stubGlobal('visualViewport', new EventTarget())
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    )
    evidenceService.deleteEvidence.mockRejectedValueOnce(new Error('Unavailable'))
    wrapper = mount(EvidenceList, {
      props: {
        evidenceList: [{ id: 2, title: '<img src=x>.txt', evidence_type: 'file' }],
        caseId: 7,
      },
      attachTo: document.body,
      global: { plugins: [createVuetify({ components, directives, theme: false })] },
    })
    await wrapper.get('[aria-label="Delete <img src=x>.txt"]').trigger('click')
    await flushPromises()
    const dialog = document.querySelector('[role="dialog"][aria-label="Confirm Deletion"]')
    expect(dialog.textContent).toContain('<img src=x>.txt')
    expect(dialog.querySelector('img')).toBeNull()
    const confirm = [...dialog.querySelectorAll('button')].find(
      (button) => button.textContent.trim() === 'Delete',
    )
    confirm.click()
    await flushPromises()
    expect(evidenceService.deleteEvidence).toHaveBeenCalledWith(2)
    expect(wrapper.get('[role="alert"]').text()).toContain('Unavailable')
    expect(wrapper.emitted('refresh')).toBeUndefined()
  })
  it('refreshes after a bulk delete that fails partway', async () => {
    vi.stubGlobal('visualViewport', new EventTarget())
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    )
    evidenceService.deleteEvidence
      .mockResolvedValueOnce()
      .mockRejectedValueOnce(new Error('Unavailable'))
    wrapper = mount(EvidenceList, {
      props: {
        evidenceList: [
          { id: 2, title: 'a.txt', evidence_type: 'file' },
          { id: 3, title: 'b.txt', evidence_type: 'file' },
        ],
        caseId: 7,
      },
      attachTo: document.body,
      global: { plugins: [createVuetify({ components, directives, theme: false })] },
    })
    await wrapper.get('[aria-label="Select a.txt"]').setValue(true)
    await wrapper.get('[aria-label="Select b.txt"]').setValue(true)
    const deleteSelected = wrapper
      .findAll('button')
      .find((button) => button.text().trim() === 'Delete Selected')
    await deleteSelected.trigger('click')
    await flushPromises()
    const dialog = document.querySelector('[role="dialog"][aria-label="Confirm Deletion"]')
    ;[...dialog.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Delete').click()
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('Unavailable')
    expect(wrapper.emitted('refresh')).toHaveLength(1)
  })
})
