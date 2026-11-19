import { createStore } from 'vuex'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import dashboardApplication from '@baserow/modules/dashboard/store/dashboardApplication'

let store
let patch
let afterSave

beforeEach(() => {
  vi.useFakeTimers()
  store = createStore({ modules: { dashboardApplication } })
  patch = vi.fn().mockResolvedValue({ data: {} })
  afterSave = vi.fn()
  store.$client = { patch }
  store.$registry = { get: () => ({ afterSave }) }
  store.commit('dashboardApplication/SET_DASHBOARD_ID', 42)
  store.commit('dashboardApplication/ADD_WIDGET', {
    id: 1,
    type: 'text_filter',
    title: 'Country',
    placeholder: '',
    target_filters: [],
  })
})

afterEach(() => {
  store.commit('dashboardApplication/RESET')
  vi.clearAllTimers()
  vi.useRealTimers()
})

const update = (values, originalValues, widgetId = 1) =>
  store.dispatch('dashboardApplication/updateWidget', {
    widgetId,
    values,
    originalValues,
  })

test('merges pending fields and resolves every caller after the combined save', async () => {
  let finishSave
  patch.mockImplementation(
    () => new Promise((resolve) => (finishSave = resolve))
  )
  const firstDone = vi.fn()
  const secondDone = vi.fn()
  const targets = [{ target_widget_id: 20 }]
  const first = update(
    { target_filters: targets },
    { target_filters: [] }
  ).then(firstDone)
  await vi.advanceTimersByTimeAsync(500)
  const second = update({ title: 'Countries' }, { title: 'Country' }).then(
    secondDone
  )
  await vi.advanceTimersByTimeAsync(999)
  expect(patch).not.toHaveBeenCalled()
  await vi.advanceTimersByTimeAsync(1)
  expect(patch).toHaveBeenCalledExactlyOnceWith('/dashboard/widgets/1/', {
    target_filters: targets,
    title: 'Countries',
  })
  expect(firstDone).not.toHaveBeenCalled()
  expect(secondDone).not.toHaveBeenCalled()
  finishSave({ data: {} })
  await Promise.all([first, second])
  expect(firstDone).toHaveBeenCalledOnce()
  expect(secondDone).toHaveBeenCalledOnce()
  expect(afterSave).toHaveBeenCalledOnce()
  expect(afterSave.mock.calls[0][2]).toEqual({
    target_filters: targets,
    title: 'Countries',
  })
})

test('keeps the latest value when the same field changes repeatedly', async () => {
  const first = update({ title: 'Countries' }, { title: 'Country' })
  const second = update({ title: 'Regions' }, { title: 'Countries' })
  await vi.advanceTimersByTimeAsync(1000)
  await Promise.all([first, second])
  expect(patch).toHaveBeenCalledExactlyOnceWith('/dashboard/widgets/1/', {
    title: 'Regions',
  })
})

test('rejects all callers and restores every original field on failure', async () => {
  const error = new Error('Save failed')
  patch.mockRejectedValueOnce(error)
  const saves = Promise.allSettled([
    update({ title: 'Countries' }, { title: 'Country' }),
    update({ placeholder: 'Choose' }, { placeholder: '' }),
    update({ title: 'Regions' }, { title: 'Countries' }),
  ])
  await vi.advanceTimersByTimeAsync(1000)
  expect(await saves).toEqual([
    { status: 'rejected', reason: error },
    { status: 'rejected', reason: error },
    { status: 'rejected', reason: error },
  ])
  expect(store.state.dashboardApplication.widgets[0]).toMatchObject({
    title: 'Country',
    placeholder: '',
  })
  expect(afterSave).not.toHaveBeenCalled()

  const retry = update({ title: 'Retry' }, { title: 'Country' })
  await vi.advanceTimersByTimeAsync(1000)
  await retry
  expect(patch).toHaveBeenLastCalledWith('/dashboard/widgets/1/', {
    title: 'Retry',
  })
})

test('settles callers even when recovery after a save error also fails', async () => {
  const error = new Error('Save failed')
  patch.mockRejectedValueOnce(error)
  store.$client.get = vi.fn().mockRejectedValue(new Error('Refresh failed'))
  const saves = Promise.allSettled([
    update({ title: 'Countries' }, { title: 'Country' }),
    update({ placeholder: 'Choose' }, { placeholder: '' }),
  ])
  store.commit('dashboardApplication/INVALIDATE_WIDGET_FETCH')
  await vi.advanceTimersByTimeAsync(1000)
  expect(await saves).toEqual([
    { status: 'rejected', reason: error },
    { status: 'rejected', reason: error },
  ])
  expect(store.$client.get).toHaveBeenCalledOnce()
})

test('keeps updates to different widgets in separate batches', async () => {
  store.commit('dashboardApplication/ADD_WIDGET', { id: 2, title: 'Revenue' })
  store.$client.get = vi.fn().mockResolvedValue({
    data: [
      { id: 1, title: 'Countries' },
      { id: 2, title: 'Sales' },
    ],
  })
  const saves = [
    update({ title: 'Countries' }, { title: 'Country' }),
    update({ title: 'Sales' }, { title: 'Revenue' }, 2),
  ]
  await vi.advanceTimersByTimeAsync(1000)
  await Promise.all(saves)
  expect(patch).toHaveBeenCalledTimes(2)
  expect(patch).toHaveBeenCalledWith('/dashboard/widgets/1/', {
    title: 'Countries',
  })
  expect(patch).toHaveBeenCalledWith('/dashboard/widgets/2/', {
    title: 'Sales',
  })
})

test('does not merge a new edit into a request already sent to the server', async () => {
  let finishFirst
  patch.mockImplementationOnce(
    () => new Promise((resolve) => (finishFirst = resolve))
  )
  store.$client.get = vi.fn().mockResolvedValue({
    data: [{ id: 1, title: 'Regions' }],
  })
  const firstDone = vi.fn()
  const first = update({ title: 'Countries' }, { title: 'Country' }).then(
    firstDone
  )
  await vi.advanceTimersByTimeAsync(1000)
  const second = update({ title: 'Regions' }, { title: 'Countries' })
  await vi.advanceTimersByTimeAsync(1000)
  await second
  expect(patch.mock.calls.map(([, values]) => values)).toEqual([
    { title: 'Countries' },
    { title: 'Regions' },
  ])
  expect(firstDone).not.toHaveBeenCalled()
  finishFirst({ data: {} })
  await first
  expect(firstDone).toHaveBeenCalledOnce()
})
