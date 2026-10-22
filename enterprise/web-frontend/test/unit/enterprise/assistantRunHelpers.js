import { vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'

export function createRunsTestApp() {
  vi.clearAllMocks()
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  sessionStorage.clear()
  const testApp = new TestApp()
  testApp.authenticate({ id: 1, first_name: 'Test' })
  const realtime = testApp.getApp().$realtime
  for (const method of ['subscribe', 'unsubscribe', 'subscribeToPage']) {
    vi.spyOn(realtime, method).mockImplementation(() => {})
  }
  return testApp
}
export async function destroyRunsTestApp(testApp) {
  await testApp.store.dispatch('chatRuns/disconnect')
  await testApp.afterEach()
  vi.restoreAllMocks()
  vi.useRealTimers()
}
export const cursor = (id) => `generation:${id}-0`
export const runRecord = (type, values = {}, metadata = {}) => ({
  type,
  ...values,
  _run: { id: 'run-1', chat_id: 7, ...metadata },
})
export const followRun = (store) =>
  store.dispatch('chatRuns/follow', {
    runId: 'run-1',
    runType: 'assistant',
    chatId: 7,
    attach: false,
  })
export const acceptRecord = (store, record, runId = 'run-1') =>
  store.dispatch('chatRuns/acceptRecord', { runId, record })
export const applySnapshot = (store, snapshot, runId = 'run-1') =>
  store.dispatch('chatRuns/applySnapshot', { runId, snapshot })
