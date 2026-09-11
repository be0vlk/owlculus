import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import { evidenceService } from '@/services/evidence'
import EvidenceList from '../EvidenceList.vue'

vi.mock('@/services/evidence', () => ({
  evidenceService: { deleteEvidence: vi.fn(), moveEvidence: vi.fn() },
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
    const data = new Map()
    const dataTransfer = {
      setData: (key, value) => data.set(key, value),
      getData: (key) => data.get(key),
      setDragImage: vi.fn(),
    }
    await wrapper.get('[draggable="true"]').trigger('dragstart', { dataTransfer })
    evidenceService.moveEvidence.mockRejectedValueOnce(new Error('Move unavailable'))
    const target = wrapper
      .findAll('.tree-item-title-wrapper')
      .find((item) => item.text() === 'Archive')
    await target.trigger('drop', { dataTransfer })
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('Move unavailable')
    expect(wrapper.emitted('evidence-moved').at(-1)[0]).toEqual(items)
  })
  it('keeps failed deletion feedback inside the confirmation dialog', async () => {
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
        evidenceList: [{ id: 2, title: 'statement.txt', evidence_type: 'file' }],
        caseId: 7,
      },
      attachTo: document.body,
      global: { plugins: [createVuetify({ components, directives, theme: false })] },
    })
    await wrapper.get('[aria-label="Delete statement.txt"]').trigger('click')
    await flushPromises()
    const dialog = document.querySelector('[role="dialog"][aria-label="Confirm Delete"]')
    const confirm = [...dialog.querySelectorAll('button')].find(
      (button) => button.textContent.trim() === 'Delete',
    )
    confirm.click()
    await flushPromises()
    expect(dialog.querySelector('[role="alert"]').textContent).toContain(
      'Failed to delete evidence',
    )
    expect(wrapper.emitted('refresh')).toBeUndefined()
  })
})
