import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { PageRouteSymbol } from '#app/components/injections'
import { TestApp } from '@baserow/test/helpers/testApp'
import AgentPage from '@baserow/modules/agent/pages/agent'

describe('Agent page', () => {
  let testApp

  beforeEach(async () => {
    testApp = new TestApp()
    await testApp.store.dispatch('application/forceCreate', {
      id: 10,
      name: 'Agent',
      type: 'agent',
      readiness: 'ready',
      workspace: { id: 1 },
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('uses the loaded application and records the visit without refetching it', async () => {
    testApp.mock.onPost('/agent/10/').reply(204)

    await testApp.mount(AgentPage, {
      global: {
        provide: { [PageRouteSymbol]: { params: { agentId: '10' } } },
        stubs: { AgentApplicationContent: true },
      },
    })
    await flushPromises()

    expect(
      testApp.mock.history.post.filter(({ url }) => url === '/agent/10/')
    ).toHaveLength(1)
    expect(testApp.mock.history.get).toHaveLength(0)
    expect(testApp.store.getters['application/get'](10)).toMatchObject({
      name: 'Agent',
      readiness: 'ready',
    })
  })
})
