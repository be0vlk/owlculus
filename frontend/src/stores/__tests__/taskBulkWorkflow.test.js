import { describe, expect, it } from 'vitest'
import { deferred, taskRecord, taskWorkflow } from '@/components/__tests__/helpers/taskWorkflow'

const operations = [
  {
    method: 'bulkAssign',
    value: 10,
    url: '/api/tasks/bulk/assign',
    payload: { task_ids: [42, 43], user_id: 10 },
    update: { assigned_to_id: 10 },
  },
  {
    method: 'bulkUpdateStatus',
    value: 'completed',
    url: '/api/tasks/bulk/status',
    payload: { task_ids: [42, 43], status: 'completed' },
    update: { status: 'completed' },
  },
]

describe.each(operations)('$method HTTP contract', ({ method, value, url, payload, update }) => {
  it.each([2, 1, 0])('applies only returned successful Tasks (%s results)', async (count) => {
    const flow = await taskWorkflow()
    const unrelated = taskRecord({ id: 99, title: 'Unrelated' })
    flow.store.tasks.push(unrelated)
    const before = structuredClone(
      flow.store.tasks.map((task) => ({
        ...task,
        assigned_to: { ...task.assigned_to },
        assigned_by: { ...task.assigned_by },
        custom_fields: { ...task.custom_fields },
      })),
    )
    const updated = [
      taskRecord(update),
      taskRecord({ id: 43, title: 'Other task', ...update }),
    ].slice(0, count)
    flow.mutations.push({ data: updated })
    await expect(flow.store[method]([42, 43], value)).resolves.toEqual(updated)
    expect(flow.writes()).toEqual([{ method: 'post', url, data: payload, params: undefined }])
    expect(flow.store.tasks).toEqual([...updated, ...before.slice(count)])
    expect(flow.store.loading).toBe(false)
    expect(flow.store.error).toBeNull()
  })

  it('exposes HTTP rejection, preserves acknowledged records, and permits retry', async () => {
    const flow = await taskWorkflow()
    const before = flow.store.tasks.map((task) => ({ ...task }))
    flow.mutations.push({ status: 403, detail: 'Bulk operation denied' })
    await expect(flow.store[method]([42, 43], value)).rejects.toMatchObject({
      response: { status: 403 },
    })
    expect(flow.store.tasks).toEqual(before)
    expect(flow.store.error).toBe('Bulk operation denied')
    expect(flow.store.loading).toBe(false)
    flow.mutations.push({ data: [taskRecord(update)] })
    await expect(flow.store[method]([42, 43], value)).resolves.toEqual([taskRecord(update)])
    expect(flow.store.tasks).toEqual([taskRecord(update), before[1]])
    expect(flow.store.error).toBeNull()
  })

  it('leaves a newly selected Case dataset untouched by a late result', async () => {
    const flow = await taskWorkflow()
    const pending = deferred()
    flow.mutations.push(pending.promise)
    const mutation = flow.store[method]([42, 43], value)
    await flow.context.select(8)
    const other = taskRecord({ id: 80, case_id: 8 })
    flow.store.tasks = [other]
    flow.store.currentTask = other
    pending.resolve({ data: [taskRecord(update), taskRecord({ id: 43, ...update })] })
    await mutation
    expect(flow.writes()[0]).toMatchObject({ url, data: payload })
    expect(flow.store.tasks).toEqual([other])
    expect(flow.store.currentTask).toEqual(other)
  })
})

it('bulk unassignment preserves the null user contract', async () => {
  const flow = await taskWorkflow()
  flow.mutations.push({ data: [taskRecord({ assigned_to_id: null, assigned_to: null })] })
  await flow.store.bulkAssign([42, 43], null)
  expect(flow.writes()[0].data).toEqual({ task_ids: [42, 43], user_id: null })
  expect(flow.store.tasks[0].assigned_to_id).toBeNull()
  expect(flow.store.tasks[1].assigned_to_id).toBe(9)
})
