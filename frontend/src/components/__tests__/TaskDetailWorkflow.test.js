import { describe, expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import TaskDetail from '@/views/tasks/TaskDetail.vue'
import {
  button,
  choose,
  deferred,
  dialog,
  field,
  taskRecord,
  taskWorkflow,
} from './helpers/taskWorkflow'

async function detail(options) {
  const flow = await taskWorkflow(options)
  const wrapper = flow.mount(TaskDetail)
  await flushPromises()
  return { ...flow, wrapper }
}

describe('Task detail through real stores and HTTP', () => {
  it.each([
    ['Admin', 1, false, 'Edit Task', true],
    ['Investigator', 2, true, 'Edit Task', true],
    ['Investigator', 9, false, 'Quick Edit', true],
    ['Investigator', 2, false, null, false],
    ['Analyst', 2, false, null, false],
  ])('offers %s user %s lead=%s the appropriate editor', async (role, id, lead, edit, assign) => {
    const flow = await detail({ user: { id, role }, lead })
    const names = flow.wrapper.findAll('button').map((item) => item.text().trim())
    expect(names.includes('Edit Task')).toBe(edit === 'Edit Task')
    expect(names.includes('Quick Edit')).toBe(edit === 'Quick Edit')
    expect(flow.wrapper.find('[aria-label="Change assignee"]').exists()).toBe(assign)
    expect(flow.writes()).toEqual([])
  })

  it('persists a full keyboard edit and synchronizes acknowledged list/detail records', async () => {
    const flow = await detail()
    await button(flow.wrapper, 'Edit Task').trigger('click')
    await flushPromises()
    const form = dialog('Edit Task')
    await field(form, 'Title').setValue('Reviewed evidence')
    await field(form, 'Description').setValue('Reviewed the source report')
    await field(form, 'Due Date').setValue('2026-10-12')
    await choose(form, 'Priority', 'High')
    const pending = deferred()
    flow.mutations.push(pending.promise)
    await form.get('form').trigger('submit')
    await flushPromises()
    expect(flow.writes()).toEqual([
      {
        method: 'put',
        url: '/api/tasks/42',
        params: undefined,
        data: {
          case_id: 7,
          title: 'Reviewed evidence',
          description: 'Reviewed the source report',
          template_id: null,
          priority: 'high',
          assigned_to_id: 9,
          due_date: '2026-10-12T00:00:00.000Z',
          custom_fields: { source: 'Original', retained: 'Keep me' },
        },
      },
    ])
    expect(flow.store.currentTask.title).toBe('Review evidence')
    await form.get('form').trigger('submit')
    await flushPromises()
    expect(flow.writes()).toHaveLength(1)
    const saved = taskRecord({
      title: 'Reviewed evidence',
      description: 'Reviewed the source report',
      priority: 'high',
      due_date: '2026-10-12T00:00:00Z',
    })
    pending.resolve({ data: saved })
    await flushPromises()
    expect(flow.store.currentTask).toEqual(saved)
    expect(flow.store.tasks[0]).toEqual(saved)
    expect(flow.store.tasks[1].title).toBe('Other task')
    expect(flow.wrapper.text()).toContain('Reviewed the source report')
    expect(flow.errors).toEqual([])
  })

  it('persists assignee quick edits and preserves custom fields outside the edited template', async () => {
    const flow = await detail({ user: { id: 9, role: 'Investigator' } })
    await button(flow.wrapper, 'Quick Edit').trigger('click')
    await flushPromises()
    const form = dialog('Quick Edit Task')
    expect(form.findAll('label').map((item) => item.text())).not.toContain('Due Date')
    await field(form, 'Source').setValue('Verified source')
    await choose(form, 'Status', 'In Progress')
    const saved = taskRecord({
      status: 'in_progress',
      custom_fields: { source: 'Verified source', retained: 'Keep me' },
    })
    flow.mutations.push({ data: saved })
    await form.get('form').trigger('submit')
    await flushPromises()
    expect(flow.writes()[0]).toMatchObject({
      url: '/api/tasks/42',
      data: { status: 'in_progress', custom_fields: saved.custom_fields },
    })
    expect(flow.store.tasks[0]).toEqual(saved)
    expect(flow.store.currentTask).toEqual(saved)
    expect(flow.wrapper.text()).toContain('Verified source')
    expect(flow.errors).toEqual([])
  })

  it('retains a rejected edit and retries from the same dialog', async () => {
    const flow = await detail()
    await button(flow.wrapper, 'Edit Task').trigger('click')
    await flushPromises()
    const form = dialog('Edit Task')
    await field(form, 'Title').setValue('Retry this edit')
    flow.mutations.push({ status: 500, detail: 'Task update temporarily unavailable' })
    await form.get('form').trigger('submit')
    await flushPromises()
    expect(flow.store.currentTask.title).toBe('Review evidence')
    expect(flow.store.tasks[0].title).toBe('Review evidence')
    expect(flow.wrapper.get('[role="alert"]').text()).toContain(
      'Task update temporarily unavailable',
    )
    expect(field(form, 'Title').element.value).toBe('Retry this edit')
    expect(flow.errors).toHaveLength(1) // The view propagates the rejection to Vue as well as displaying store.error.
    flow.mutations.push({ data: taskRecord({ title: 'Retry this edit' }) })
    await form.get('form').trigger('submit')
    await flushPromises()
    expect(flow.writes()).toHaveLength(2)
    expect(flow.store.currentTask.title).toBe('Retry this edit')
    expect(flow.store.error).toBeNull()
  })

  it('saves a single custom field while retaining unrelated values', async () => {
    const flow = await detail()
    const sourceRow = flow.wrapper
      .findAll('.d-flex.align-center.mb-1')
      .find((item) => item.text().trim() === 'Source')
    const edit = sourceRow.get('button')
    await edit.trigger('click')
    await flushPromises()
    await field(flow.wrapper, 'Source').setValue('New source')
    const saved = taskRecord({ custom_fields: { source: 'New source', retained: 'Keep me' } })
    flow.mutations.push({ data: saved })
    await button(flow.wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(flow.writes()[0].data).toEqual({ custom_fields: saved.custom_fields })
    expect(flow.store.currentTask).toEqual(saved)
    expect(flow.store.tasks[0]).toEqual(saved)
  })

  it('keeps an in-flight edit targeted to the original Task after a Case change', async () => {
    const flow = await detail()
    await button(flow.wrapper, 'Edit Task').trigger('click')
    await flushPromises()
    const form = dialog('Edit Task')
    await field(form, 'Title').setValue('Old Case update')
    const pending = deferred()
    flow.mutations.push(pending.promise)
    await form.get('form').trigger('submit')
    await flushPromises()
    await flow.context.select(8)
    await flow.router.push('/case/8/tasks/80')
    const other = taskRecord({ id: 80, case_id: 8, title: 'Current Case task' })
    flow.store.tasks = [other]
    flow.store.currentTask = other
    pending.resolve({ data: taskRecord({ title: 'Old Case update' }) })
    await flushPromises()
    expect(flow.writes()[0]).toMatchObject({ url: '/api/tasks/42', data: { case_id: 7 } })
    expect(flow.store.tasks).toEqual([other])
    expect(flow.store.currentTask).toEqual(other)
    expect(flow.wrapper.text()).toContain('Current Case task')
    expect(flow.wrapper.text()).not.toContain('Old Case update')
  })
})

it('retains a rejected assignee quick edit and saves it on retry', async () => {
  const flow = await detail({ user: { id: 9, role: 'Investigator' } })
  await button(flow.wrapper, 'Quick Edit').trigger('click')
  await flushPromises()
  const form = dialog('Quick Edit Task')
  await field(form, 'Source').setValue('Retry source')
  flow.mutations.push({ status: 403, detail: 'Task edit denied' })
  await form.get('form').trigger('submit')
  await flushPromises()
  expect(flow.store.currentTask.custom_fields.source).toBe('Original')
  expect(flow.store.tasks[0].custom_fields.source).toBe('Original')
  expect(flow.wrapper.get('[role="alert"]').text()).toContain('Task edit denied')
  expect(field(form, 'Source').element.value).toBe('Retry source')
  flow.mutations.push({
    data: taskRecord({ custom_fields: { source: 'Retry source', retained: 'Keep me' } }),
  })
  await form.get('form').trigger('submit')
  await flushPromises()
  expect(flow.store.currentTask.custom_fields.source).toBe('Retry source')
  expect(flow.writes()).toHaveLength(2)
  expect(flow.errors).toHaveLength(1)
})

it.each(['assignment', 'status'])(
  'retries a rejected detail %s through the open dialog',
  async (operation) => {
    const flow = await detail()
    if (operation === 'assignment') await button(flow.wrapper, 'Change assignee').trigger('click')
    else
      await flow.wrapper
        .findAll('.v-chip')
        .find((chip) => chip.text() === 'Not Started')
        .trigger('click')
    await flushPromises()
    const form = dialog(operation === 'assignment' ? 'Assign Task' : 'Update Status')
    await choose(
      form,
      operation === 'assignment' ? 'Assign To' : 'New Status',
      operation === 'assignment' ? 'new-owner' : 'Completed',
    )
    flow.mutations.push({ status: 403, detail: 'This operation is denied' })
    await button(form, operation === 'assignment' ? 'Assign' : 'Update').trigger('click')
    await flushPromises()
    expect(flow.wrapper.get('[role="alert"]').text()).toContain('This operation is denied')
    expect(flow.store.currentTask).toEqual(taskRecord())
    expect(flow.store.tasks[0]).toEqual(taskRecord())
    const saved = taskRecord(
      operation === 'assignment'
        ? { assigned_to_id: 10, assigned_to: { id: 10, username: 'new-owner' } }
        : { status: 'completed' },
    )
    flow.mutations.push({ data: saved })
    await button(form, operation === 'assignment' ? 'Assign' : 'Update').trigger('click')
    await flushPromises()
    expect(flow.store.currentTask).toEqual(saved)
    expect(flow.store.tasks[0]).toEqual(saved)
    expect(flow.writes()).toHaveLength(2)
    expect(flow.errors).toHaveLength(1)
  },
)

it.fails(
  'retains acknowledged custom fields after a full edit is rejected (03-tasks-custom-field-draft)',
  async () => {
    const flow = await detail()
    await button(flow.wrapper, 'Edit Task').trigger('click')
    await flushPromises()
    const form = dialog('Edit Task')
    await field(form, 'Source').setValue('Unsaved source')
    flow.mutations.push({ status: 500, detail: 'Edit rejected' })
    await form.get('form').trigger('submit')
    await flushPromises()
    expect(flow.writes()[0].data.custom_fields).toEqual({
      source: 'Unsaved source',
      retained: 'Keep me',
    })
    expect(flow.wrapper.get('[role="alert"]').text()).toContain('Edit rejected')
    expect(flow.store.currentTask.custom_fields).toEqual({
      source: 'Original',
      retained: 'Keep me',
    })
  },
)

it.fails(
  'denies quick editing to an assigned Analyst under the backend read-only policy (03-tasks-analyst-controls)',
  async () => {
    const flow = await detail({ user: { id: 9, role: 'Analyst' } })
    expect(flow.writes()).toEqual([])
    expect(flow.wrapper.findAll('button').some((item) => item.text().trim() === 'Quick Edit')).toBe(
      false,
    )
  },
)
