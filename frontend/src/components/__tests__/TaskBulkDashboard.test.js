import { describe, expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import TaskDashboard from '@/views/tasks/TaskDashboard.vue'
import { useAuthStore } from '@/stores/auth'
import {
  button,
  choose,
  deferred,
  dialog,
  field,
  taskRecord,
  taskWorkflow,
} from './helpers/taskWorkflow'

async function dashboard(options) {
  const flow = await taskWorkflow(options)
  const wrapper = flow.mount(TaskDashboard)
  await flushPromises()
  await wrapper
    .findAll('.v-chip')
    .find((chip) => chip.text().trim() === 'All Tasks')
    .trigger('click')
  await flushPromises()
  await wrapper.get('thead input[type="checkbox"]').setValue(true)
  await flushPromises()
  return { ...flow, wrapper }
}

describe('Task dashboard bulk actions', () => {
  it('submits selected IDs once and updates the list, detail, and statistics', async () => {
    const flow = await dashboard()
    flow.store.currentTask = taskRecord()
    expect(flow.wrapper.text()).toContain('2 Tasks selected')
    await button(flow.wrapper, 'Bulk Update Status').trigger('click')
    await flushPromises()
    const form = dialog('Bulk Update Status')
    expect(button(form, 'Apply').attributes('disabled')).toBeDefined()
    await choose(form, 'New Status', 'Completed')
    expect(flow.writes()).toEqual([])
    flow.mutations.push({
      data: [taskRecord({ status: 'completed' }), taskRecord({ id: 43, status: 'completed' })],
    })
    await form.get('form').trigger('submit')
    await flushPromises()
    expect(flow.writes()).toEqual([
      {
        method: 'post',
        url: '/api/tasks/bulk/status',
        params: undefined,
        data: { task_ids: [42, 43], status: 'completed' },
      },
    ])
    expect(flow.store.currentTask.status).toBe('completed')
    expect(flow.store.stats.completed).toBe(2)
    expect(document.body.textContent).toContain('2 Tasks updated')
    expect(flow.wrapper.text()).not.toContain('Tasks selected')
    expect(flow.errors).toEqual([])
  })
})

it.each([
  ['Not Started', 'not_started'],
  ['In Progress', 'in_progress'],
  ['Blocked', 'blocked'],
  ['Completed', 'completed'],
])('supports explicit status %s', async (title, status) => {
  const flow = await dashboard()
  await button(flow.wrapper, 'Bulk Update Status').trigger('click')
  await flushPromises()
  const form = dialog('Bulk Update Status')
  await form.get('form').trigger('submit')
  expect(flow.writes()).toEqual([])
  await choose(form, 'New Status', title)
  flow.mutations.push({ data: flow.records.map((task) => ({ ...task, status })) })
  await form.get('form').trigger('submit')
  await flushPromises()
  expect(flow.writes()[0].data).toEqual({ task_ids: [42, 43], status })
  expect(flow.store.tasks.every((task) => task.status === status)).toBe(true)
})

it.each([
  ['new-owner', 10],
  ['Unassigned', null],
])('assigns to %s with an explicit choice', async (title, userId) => {
  const flow = await dashboard()
  await button(flow.wrapper, 'Bulk Assign').trigger('click')
  await flushPromises()
  const form = dialog('Bulk Assign')
  await form.get('form').trigger('submit')
  expect(flow.writes()).toEqual([])
  expect(form.text()).toContain('2 Tasks targeted')
  await choose(form, 'Assign To', title)
  flow.mutations.push({
    data: flow.records.map((task) => ({
      ...task,
      assigned_to_id: userId,
      assigned_to: userId ? { id: userId, username: title } : null,
    })),
  })
  await form.get('form').trigger('submit')
  await flushPromises()
  expect(flow.writes()[0].data).toEqual({ task_ids: [42, 43], user_id: userId })
  expect(flow.store.tasks.every((task) => task.assigned_to_id === userId)).toBe(true)
})

it.each(['Bulk Assign', 'Bulk Update Status'])(
  'cancels %s without mutation and discards its choice',
  async (name) => {
    const flow = await dashboard()
    await button(flow.wrapper, name).trigger('click')
    await flushPromises()
    const form = dialog(name)
    await choose(
      form,
      name === 'Bulk Assign' ? 'Assign To' : 'New Status',
      name === 'Bulk Assign' ? 'Unassigned' : 'Completed',
    )
    await button(form, 'Cancel').trigger('click')
    await flushPromises()
    await button(flow.wrapper, name).trigger('click')
    await flushPromises()
    expect(button(dialog(name), 'Apply').attributes('disabled')).toBeDefined()
    expect(flow.writes()).toEqual([])
  },
)

it.each([
  ['Admin', false, true, true],
  ['Investigator', true, true, true],
  ['Investigator', false, false, true],
  ['Analyst', true, false, false],
])('uses Case membership for %s (lead %s)', async (role, lead, assign, status) => {
  const flow = await dashboard({ user: { id: 2, role }, lead })
  expect(button(flow.wrapper, 'Bulk Assign').attributes('disabled') === undefined).toBe(assign)
  expect(button(flow.wrapper, 'Bulk Update Status').attributes('disabled') === undefined).toBe(
    status,
  )
  expect(flow.writes()).toEqual([])
})

it('retries a failed assignee load instead of showing an empty list', async () => {
  const flow = await dashboard()
  flow.reads.set('/api/cases/7/users', [{ status: 500 }])
  await button(flow.wrapper, 'Bulk Assign').trigger('click')
  await flushPromises()
  const form = dialog('Bulk Assign')
  expect(form.text()).toContain('Unable to load Case users')
  expect(button(form, 'Apply').attributes('disabled')).toBeDefined()
  await button(form, 'Retry users').trigger('click')
  await flushPromises()
  await choose(form, 'Assign To', 'new-owner')
  expect(button(form, 'Apply').attributes('disabled')).toBeUndefined()
  expect(flow.writes()).toEqual([])
})

it.each([0, 1])('reports %s successes and retries only remaining available IDs', async (count) => {
  const flow = await dashboard()
  await button(flow.wrapper, 'Bulk Update Status').trigger('click')
  await flushPromises()
  const form = dialog('Bulk Update Status')
  await choose(form, 'New Status', 'Completed')
  const updated = count ? [taskRecord({ status: 'completed' })] : []
  if (count) flow.records[0] = updated[0]
  flow.mutations.push({ data: updated })
  await form.get('form').trigger('submit')
  await flushPromises()
  expect(form.text()).toContain(`${count} Tasks updated; ${2 - count} not updated`)
  expect(form.text()).toContain(`${2 - count} Tasks targeted`)
  expect(field(form, 'New Status').element.value).toBe('Completed')
  flow.mutations.push({ data: flow.records.map((task) => ({ ...task, status: 'completed' })) })
  await form.get('form').trigger('submit')
  await flushPromises()
  expect(flow.writes()[1].data).toEqual({ task_ids: count ? [43] : [42, 43], status: 'completed' })
})

it('removes deleted Tasks after a partial result while reporting them as not updated', async () => {
  const flow = await dashboard()
  await button(flow.wrapper, 'Bulk Assign').trigger('click')
  await flushPromises()
  const form = dialog('Bulk Assign')
  await choose(form, 'Assign To', 'Unassigned')
  flow.records.splice(1, 1)
  flow.records[0] = taskRecord({ assigned_to_id: null, assigned_to: null })
  flow.mutations.push({ data: [flow.records[0]] })
  await form.get('form').trigger('submit')
  await flushPromises()
  expect(form.text()).toContain('1 Tasks updated; 1 not updated')
  expect(form.text()).toContain('0 Tasks targeted')
  expect(button(form, 'Apply').attributes('disabled')).toBeDefined()
  await form.get('form').trigger('submit')
  expect(flow.writes()).toHaveLength(1)
})

it.each([403, 500])(
  'reconciles a %s failure and permits deliberate retry without claiming rollback',
  async (status) => {
    const flow = await dashboard()
    await button(flow.wrapper, 'Bulk Update Status').trigger('click')
    await flushPromises()
    const form = dialog('Bulk Update Status')
    await choose(form, 'New Status', 'Completed')
    flow.records[0] = taskRecord({ status: 'completed' })
    flow.mutations.push({ status, detail: 'Updates unavailable' })
    await form.get('form').trigger('submit')
    await flushPromises()
    expect(form.text()).toContain('Updates unavailable. Some Tasks may have changed')
    expect(flow.store.tasks[0].status).toBe('completed')
    expect(form.text()).toContain('2 Tasks targeted')
    flow.mutations.push({ data: flow.records.map((task) => ({ ...task, status: 'completed' })) })
    await form.get('form').trigger('submit')
    await flushPromises()
    expect(flow.writes()).toHaveLength(2)
    expect(flow.writes()[1].data.task_ids).toEqual([42, 43])
  },
)

it('holds pending state through the HTTP response and blocks repeated keyboard confirmation', async () => {
  const flow = await dashboard()
  await button(flow.wrapper, 'Bulk Assign').trigger('click')
  await flushPromises()
  const form = dialog('Bulk Assign')
  await choose(form, 'Assign To', 'Unassigned')
  const pending = deferred()
  flow.mutations.push(pending.promise)
  await form.get('form').trigger('submit')
  await form.get('form').trigger('submit')
  await flushPromises()
  expect(flow.writes()).toHaveLength(1)
  expect(form.text()).toContain('Applying Task updates')
  expect(button(form, 'Cancel').attributes('disabled')).toBeDefined()
  expect(button(flow.wrapper, 'Bulk Update Status').attributes('disabled')).toBeDefined()
  pending.resolve({ data: flow.records.map((task) => ({ ...task, assigned_to_id: null })) })
  await flushPromises()
  expect(document.body.textContent).toContain('2 Tasks updated')
})

it('prunes selection when searching, refreshing, or clearing Case context', async () => {
  const flow = await dashboard()
  await field(flow.wrapper, 'Search tasks...').setValue('Review')
  await flushPromises()
  expect(flow.wrapper.text()).toContain('1 Tasks selected')
  await button(flow.wrapper, 'Bulk Assign').trigger('click')
  await flushPromises()
  await choose(dialog('Bulk Assign'), 'Assign To', 'Unassigned')
  await flow.context.select(8)
  await flushPromises()
  expect(document.body.textContent).not.toContain('Tasks targeted')
  expect(flow.wrapper.text()).not.toContain('Tasks selected')
  expect(flow.writes()).toEqual([])
})

it.each(['case', 'logout', 'unmount'])('ignores late responses after %s', async (leave) => {
  const flow = await dashboard()
  await button(flow.wrapper, 'Bulk Update Status').trigger('click')
  await flushPromises()
  const form = dialog('Bulk Update Status')
  await choose(form, 'New Status', 'Completed')
  const pending = deferred()
  flow.mutations.push(pending.promise)
  await form.get('form').trigger('submit')
  await flushPromises()
  if (leave === 'case') await flow.context.select(8)
  else if (leave === 'logout') useAuthStore(flow.pinia).user = null
  else flow.wrapper.unmount()
  const other = taskRecord({ case_id: leave === 'case' ? 8 : 7 })
  flow.store.tasks = [other]
  flow.store.currentTask = other
  pending.resolve({ data: [taskRecord({ status: 'completed' })] })
  await flushPromises()
  expect(flow.store.tasks).toEqual([other])
  expect(flow.store.currentTask).toEqual(other)
  expect(document.body.textContent).not.toContain('Tasks updated')
  expect(flow.writes()[0].data.task_ids).toEqual([42, 43])
})

it('requires a successful refresh before retrying an uncertain result', async () => {
  const flow = await dashboard()
  await button(flow.wrapper, 'Bulk Update Status').trigger('click')
  await flushPromises()
  const form = dialog('Bulk Update Status')
  await choose(form, 'New Status', 'Completed')
  flow.mutations.push({ status: 500, detail: 'Interrupted response' })
  flow.reads.set('/api/tasks/', [{ status: 500, detail: 'Refresh unavailable' }])
  await form.get('form').trigger('submit')
  await flushPromises()
  expect(form.text()).toContain('Refresh before retrying')
  expect(button(form, 'Apply').attributes('disabled')).toBeDefined()
  await form.get('form').trigger('submit')
  expect(flow.writes()).toHaveLength(1)
  flow.records.splice(1, 1)
  await button(form, 'Refresh Tasks').trigger('click')
  await flushPromises()
  expect(form.text()).toContain('1 Tasks targeted')
  flow.mutations.push({ data: [taskRecord({ status: 'completed' })] })
  await form.get('form').trigger('submit')
  await flushPromises()
  expect(flow.writes()[1].data.task_ids).toEqual([42])
})

it.each(['success', 'error'])(
  'leaves a new dialog intact after returning to the same Case (%s)',
  async (outcome) => {
    const flow = await dashboard()
    await button(flow.wrapper, 'Bulk Update Status').trigger('click')
    await flushPromises()
    await choose(dialog('Bulk Update Status'), 'New Status', 'Completed')
    const pending = deferred()
    flow.mutations.push(pending.promise)
    await dialog('Bulk Update Status').get('form').trigger('submit')
    await flushPromises()
    await flow.context.select(8)
    await flow.context.select(7)
    await flow.store.loadTasks()
    await flushPromises()
    await flow.wrapper.get('thead input[type="checkbox"]').setValue(true)
    await button(flow.wrapper, 'Bulk Assign').trigger('click')
    await flushPromises()
    await choose(dialog('Bulk Assign'), 'Assign To', 'Unassigned')
    pending.resolve(
      outcome === 'success'
        ? { data: [taskRecord({ status: 'completed' })] }
        : { status: 500, detail: 'Old failure' },
    )
    await flushPromises()
    expect(dialog('Bulk Assign').text()).toContain('2 Tasks targeted')
    expect(field(dialog('Bulk Assign'), 'Assign To').element.value).toBe('Unassigned')
    expect(flow.store.tasks[0].status).toBe('not_started')
    expect(flow.store.error).toBeNull()
    expect(document.body.textContent).not.toContain('Old failure')
    expect(document.body.textContent).not.toContain('Tasks updated')
  },
)

it('denies an Investigator without resolved membership and allows a user-list retry', async () => {
  const flow = await taskWorkflow({ user: { id: 2, role: 'Investigator' } })
  flow.reads.set('/api/cases/7/users', [{ status: 500 }])
  const wrapper = flow.mount(TaskDashboard)
  await flushPromises()
  await wrapper
    .findAll('.v-chip')
    .find((chip) => chip.text().trim() === 'All Tasks')
    .trigger('click')
  await wrapper.get('thead input[type="checkbox"]').setValue(true)
  await flushPromises()
  expect(button(wrapper, 'Bulk Update Status').attributes('disabled')).toBeDefined()
  await button(wrapper, 'Retry users').trigger('click')
  await flushPromises()
  expect(button(wrapper, 'Bulk Update Status').attributes('disabled')).toBeUndefined()
})

it('prunes refreshed and deselected rows before confirming an open draft', async () => {
  const flow = await dashboard()
  await flow.wrapper
    .findAll('tbody tr')
    .find((row) => row.text().includes('Other task'))
    .get('input[type="checkbox"]')
    .trigger('click')
  await button(flow.wrapper, 'Bulk Assign').trigger('click')
  await flushPromises()
  const form = dialog('Bulk Assign')
  await choose(form, 'Assign To', 'Unassigned')
  flow.records.splice(0, 1)
  await flow.store.loadTasks()
  await flushPromises()
  expect(form.text()).toContain('0 Tasks targeted')
  await form.get('form').trigger('submit')
  expect(flow.writes()).toEqual([])
})

it.each(['success', 'error'])(
  'ignores reconciliation %s after leaving the dashboard',
  async (outcome) => {
    const flow = await dashboard()
    await button(flow.wrapper, 'Bulk Update Status').trigger('click')
    await flushPromises()
    await choose(dialog('Bulk Update Status'), 'New Status', 'Completed')
    const refresh = deferred()
    flow.reads.set('/api/tasks/', [refresh.promise])
    flow.mutations.push({ data: [] })
    await dialog('Bulk Update Status').get('form').trigger('submit')
    await flushPromises()
    flow.wrapper.unmount()
    const newer = taskRecord({ title: 'Edited on detail page' })
    flow.store.tasks = [newer]
    flow.store.currentTask = newer
    refresh.resolve(
      outcome === 'success'
        ? { data: [taskRecord()] }
        : { status: 500, detail: 'Old refresh failed' },
    )
    await flushPromises()
    expect(flow.store.tasks).toEqual([newer])
    expect(flow.store.currentTask).toEqual(newer)
    expect(flow.store.error).toBeNull()
  },
)
