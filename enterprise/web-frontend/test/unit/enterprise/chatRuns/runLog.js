import { vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'

export function createRunsTestApp() {
  vi.clearAllMocks()
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  sessionStorage.clear()
  const testApp = new TestApp()
  // Kuma execution and recovery do not depend on any feature flag.
  testApp.store.app = Object.create(testApp.getApp(), {
    $featureFlagIsEnabled: { value: () => false },
  })
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
  testApp.store.app = testApp.getApp()
  vi.restoreAllMocks()
  vi.useRealTimers()
}
export const cursor = (id) => `generation:${id}-0`
export const runRecord = (type, values = {}, metadata = {}) => ({
  type,
  ...values,
  _run: { id: 'run-1', chat_id: 7, ...metadata },
})
