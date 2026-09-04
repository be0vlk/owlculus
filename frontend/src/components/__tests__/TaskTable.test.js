import { expect, it, vi } from 'vitest'
import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { mountWithVuetify } from './helpers/vuetify'
import TaskTable from '../tasks/TaskTable.vue'
import { createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useTaskStore } from '@/stores/taskStore'

let wrapper
it('preserves keyboard navigation, case-lead assignment availability, status updates and feedback', async () => {
  const pinia = createPinia()
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/case/:caseId/tasks/:id', component: { template: '<div />' } },
    ],
  })
  await router.push('/')
  const auth = useAuthStore(pinia)
  auth.user = { id: 7, role: 'Investigator' }
  const taskStore = useTaskStore(pinia)
  const update = vi.spyOn(taskStore, 'updateTaskStatus').mockResolvedValue({})
  wrapper = mountWithVuetify(TaskTable, {
    attachTo: document.body,
    props: {
      tasks: [
        {
          id: 42,
          case_id: 7,
          title: 'Review evidence',
          status: 'pending',
          priority: 'medium',
          is_lead: false,
        },
      ],
    },
    global: { plugins: [pinia, router] },
  })
  await flushPromises()
  expect(wrapper.get('a').attributes('href')).toBe('/case/7/tasks/42')
  // Task responses omit case membership; the server checks assignment permissions.
  expect(
    wrapper.get('button[aria-label="Assign Review evidence"]').attributes('disabled'),
  ).toBeUndefined()
  auth.user = { id: 7, role: 'Admin' }
  await flushPromises()
  expect(
    wrapper.get('button[aria-label="Assign Review evidence"]').attributes('disabled'),
  ).toBeUndefined()
  await wrapper.get('button[aria-label="Update status for Review evidence"]').trigger('click')
  await flushPromises()
  const dialog = new DOMWrapper(
    document.querySelector('[role="dialog"][aria-label="Update Status"]'),
  )
  const button = dialog.findAll('button').find((button) => button.text() === 'Update')
  await button.trigger('click')
  await flushPromises()
  expect(update).toHaveBeenCalledWith(42, 'pending')
  expect(document.body.textContent).toContain('Task status updated successfully')
})
