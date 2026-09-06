import { describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import CaseTasks from '@/views/cases/CaseTasks.vue'
import { useAuthStore } from '@/stores/auth'
import { button, choose, deferred, dialog, taskRecord, taskWorkflow } from './helpers/taskWorkflow'

async function table(options) {
  const flow = await taskWorkflow(options)
  const wrapper = flow.mount(CaseTasks, { caseId: 7 })
  flow.store.currentTask = taskRecord()
  await flushPromises()
  vi.spyOn(console, 'error').mockImplementation(() => {})
  return { ...flow, wrapper }
}

describe('Task table mutation integration', () => {
  it.each(['Admin', 'Investigator', 'Analyst'])(
    'shows %s creation and deletion controls',
    async (role) => {
      const flow = await table({ user: { id: 2, role } })
      expect(flow.wrapper.findAll('button').some((item) => item.text() === 'New Task')).toBe(
        role !== 'Analyst',
      )
      expect(flow.wrapper.find('[aria-label="Delete Review evidence"]').exists()).toBe(
        role === 'Admin',
      )
      // Task responses omit membership. Assignment remains available for server authorization.
      expect(
        flow.wrapper.get('[aria-label="Assign Review evidence"]').attributes('disabled'),
      ).toBeUndefined()
      expect(flow.writes()).toEqual([])
    },
  )

  it('waits for status acknowledgement, preserves a rejection, and retries successfully', async () => {
    const flow = await table()
    await button(flow.wrapper, 'Update status for Review evidence').trigger('click')
    await flushPromises()
    const form = dialog('Update Status')
    await choose(form, 'New Status', 'Completed')
    const pending = deferred()
    flow.mutations.push(pending.promise)
    await button(form, 'Update').trigger('click')
    await flushPromises()
    expect(flow.writes()[0]).toEqual({
      method: 'put',
      url: '/api/tasks/42/status',
      params: { status: 'completed' },
      data: null,
    })
    expect(flow.store.currentTask.status).toBe('not_started')
    expect(document.body.textContent).not.toContain('Task status updated successfully')
    pending.resolve({ status: 500, detail: 'Status service unavailable' })
    await flushPromises()
    expect(document.body.textContent).toContain('Status service unavailable')
    expect(flow.store.tasks[0].status).toBe('not_started')
    flow.mutations.push({ data: taskRecord({ status: 'completed' }) })
    await button(form, 'Update').trigger('click')
    await flushPromises()
    expect(flow.store.currentTask.status).toBe('completed')
    expect(flow.store.tasks[0].status).toBe('completed')
    expect(document.body.textContent).toContain('Task status updated successfully')
    expect(flow.writes()).toHaveLength(2)
  })

  it.each([403, 500])(
    'retains denied assignment (%s), reports feedback, and supports assign/unassign retry',
    async (status) => {
      const flow = await table({ user: { id: 2, role: status === 403 ? 'Investigator' : 'Admin' } })
      await button(flow.wrapper, 'Assign Review evidence').trigger('click')
      await flushPromises()
      const form = dialog('Assign Task')
      await choose(form, 'Assign To', 'new-owner')
      flow.mutations.push({ status, detail: 'Assignment unavailable' })
      await button(form, 'Assign').trigger('click')
      await flushPromises()
      expect(flow.store.tasks[0].assigned_to_id).toBe(9)
      expect(flow.store.currentTask.assigned_to_id).toBe(9)
      expect(document.body.textContent).toContain(
        status === 403 ? 'Only admins and case leads can assign tasks.' : 'Assignment unavailable',
      )
      expect(document.body.textContent).not.toContain('Task assigned successfully')
      // Model refreshed authorization before retrying a permission rejection.
      if (status === 403) useAuthStore(flow.pinia).user = { id: 2, role: 'Admin' }
      const saved = taskRecord({
        assigned_to_id: 10,
        assigned_to: { id: 10, username: 'new-owner' },
      })
      flow.mutations.push({ data: saved })
      await button(form, 'Assign').trigger('click')
      await flushPromises()
      expect(flow.store.tasks[0]).toEqual(saved)
      expect(flow.store.currentTask).toEqual(saved)
      expect(flow.writes()[1]).toEqual({
        method: 'post',
        url: '/api/tasks/42/assign',
        data: null,
        params: { user_id: 10 },
      })
      await button(flow.wrapper, 'Assign Review evidence').trigger('click')
      await flushPromises()
      const unassign = dialog('Assign Task')
      await unassign.get('[aria-label="Clear Assign To"]').trigger('click')
      await flushPromises()
      flow.mutations.push({ data: taskRecord({ assigned_to_id: null, assigned_to: null }) })
      await button(unassign, 'Unassign').trigger('click')
      await flushPromises()
      expect(flow.writes()[2].params).toEqual({ user_id: null })
      expect(flow.store.currentTask.assigned_to_id).toBeNull()
      expect(flow.store.tasks[0].assigned_to).toBeNull()
    },
  )

  it('reports a denied status transition without changing the acknowledged Task', async () => {
    const flow = await table({ user: { id: 2, role: 'Analyst' } })
    await button(flow.wrapper, 'Update status for Review evidence').trigger('click')
    await flushPromises()
    flow.mutations.push({ status: 403, detail: 'Forbidden' })
    await button(dialog('Update Status'), 'Update').trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('You do not have permission to update this task')
    expect(flow.store.tasks[0]).toEqual(taskRecord())
    expect(flow.store.currentTask).toEqual(taskRecord())
  })

  it('cancels deletion without HTTP, then removes only the confirmed Task after acknowledgement', async () => {
    const flow = await table()
    await button(flow.wrapper, 'Delete Review evidence').trigger('click')
    await flushPromises()
    await button(dialog('Confirm Deletion'), 'Cancel').trigger('click')
    await flushPromises()
    expect(flow.writes()).toEqual([])
    await button(flow.wrapper, 'Delete Review evidence').trigger('click')
    await flushPromises()
    const pending = deferred()
    flow.mutations.push(pending.promise)
    await button(dialog('Confirm Deletion'), 'Delete').trigger('click')
    await flushPromises()
    expect(flow.store.tasks).toHaveLength(2)
    pending.resolve({ data: { message: 'Deleted' } })
    await flushPromises()
    expect(flow.writes()).toEqual([
      { method: 'delete', url: '/api/tasks/42', params: undefined, data: null },
    ])
    expect(flow.store.tasks.map((task) => task.id)).toEqual([43])
    expect(flow.store.currentTask).toBeNull()
    expect(flow.wrapper.text()).not.toContain('Review evidence')
  })

  it('retains state after a rejected delete and allows a fresh confirmation to retry', async () => {
    const flow = await table()
    await button(flow.wrapper, 'Delete Review evidence').trigger('click')
    await flushPromises()
    flow.mutations.push({ status: 500, detail: 'Deletion unavailable' })
    await button(dialog('Confirm Deletion'), 'Delete').trigger('click')
    await flushPromises()
    expect(flow.store.tasks).toHaveLength(2)
    expect(flow.store.currentTask).toEqual(taskRecord())
    expect(flow.store.error).toBe('Deletion unavailable')
    await button(flow.wrapper, 'Delete Review evidence').trigger('click')
    await flushPromises()
    flow.mutations.push({ data: { message: 'Deleted' } })
    await button(dialog('Confirm Deletion'), 'Delete').trigger('click')
    await flushPromises()
    expect(flow.store.tasks.map((task) => task.id)).toEqual([43])
    expect(flow.writes()).toHaveLength(2)
  })

  it.fails(
    'shows useful feedback when confirmed deletion fails (03-tasks-delete-feedback)',
    async () => {
      const flow = await table()
      await button(flow.wrapper, 'Delete Review evidence').trigger('click')
      await flushPromises()
      flow.mutations.push({ status: 500, detail: 'Deletion unavailable' })
      await button(dialog('Confirm Deletion'), 'Delete').trigger('click')
      await flushPromises()
      expect(document.body.textContent).toContain('Deletion unavailable')
    },
  )
})
