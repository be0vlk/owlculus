import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useActiveCaseStore } from '../activeCase'
import { useTaskStore } from '../taskStore'
import { caseService } from '@/services/case'
import taskService from '@/services/task'

vi.mock('@/services/case', () => ({ caseService: { getCases: vi.fn() } }))
vi.mock('@/services/task', () => ({ default: { getTasks: vi.fn(), createTask: vi.fn() } }))
beforeEach(async () => {
  vi.clearAllMocks()
  localStorage.clear()
  setActivePinia(createPinia())
  caseService.getCases.mockResolvedValue([{ id: 1 }, { id: 2 }])
  await useActiveCaseStore().initialize(1)
})

it('scopes task datasets and statistics and discards a response from the previous case', async () => {
  const store = useTaskStore()
  let finish
  taskService.getTasks.mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve
    }),
  )
  const oldRequest = store.loadTasks()
  expect(taskService.getTasks).toHaveBeenCalledWith({ case_id: 1 })
  await useActiveCaseStore().select(2)
  taskService.getTasks.mockResolvedValueOnce([{ id: 20, case_id: 2, status: 'completed' }])
  await store.loadTasks()
  finish([{ id: 10, case_id: 1 }])
  await oldRequest
  expect(store.tasks.map((task) => task.id)).toEqual([20])
  expect(store.stats).toMatchObject({ total: 1, completed: 1 })
  useActiveCaseStore().reset()
  await store.loadTasks()
  expect(taskService.getTasks).toHaveBeenCalledTimes(2)
  expect(store.stats.total).toBe(0)
})

it('creates in the active case and rejects stale drafts or missing context', async () => {
  const store = useTaskStore()
  taskService.createTask.mockResolvedValue({ id: 3, case_id: 1 })
  await store.createTask({ title: 'Review' })
  expect(taskService.createTask).toHaveBeenCalledWith({ title: 'Review', case_id: 1 })
  await useActiveCaseStore().select(2)
  await expect(store.createTask({ title: 'Old draft', case_id: 1 })).rejects.toThrow('active case')
  useActiveCaseStore().reset()
  await expect(store.createTask({ title: 'No case' })).rejects.toThrow('active case')
  expect(taskService.createTask).toHaveBeenCalledTimes(1)
})
