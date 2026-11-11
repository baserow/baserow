import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('Application realtime updates', () => {
  let testApp, application

  beforeEach(async () => {
    testApp = new TestApp()
    application = await testApp.store.dispatch('application/forceCreate', {
      id: 1,
      type: 'agent',
      name: 'Support agent',
      readiness: 'ready',
      workspace: { id: 1 },
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('tracks every external update while preserving the application object', async () => {
    expect(application._.realtimeVersion).toBe(0)
    expect(application._.viaRealtime).toBe(false)

    for (let version = 1; version <= 2; version++) {
      await testApp.store.dispatch('application/forceUpdate', {
        application,
        data: { readiness: 'ready' },
        viaRealtime: true,
      })

      expect(testApp.store.getters['application/get'](1)).toBe(application)
      expect(application._.realtimeVersion).toBe(version)
      expect(application._.viaRealtime).toBe(true)
    }
  })

  test('local metadata updates do not advance the external version', async () => {
    await testApp.store.dispatch('application/forceUpdate', {
      application,
      data: { readiness: 'ready' },
      viaRealtime: true,
    })
    await testApp.store.dispatch('application/forceUpdate', {
      application,
      data: { last_viewed: '2026-10-22T12:00:00Z' },
    })

    expect(application.last_viewed).toBe('2026-10-22T12:00:00Z')
    expect(application._.realtimeVersion).toBe(1)
    expect(application._.viaRealtime).toBe(false)
  })
})
