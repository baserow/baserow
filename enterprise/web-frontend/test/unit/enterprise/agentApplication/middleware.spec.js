import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import { selectAgentApplication } from '@baserow_enterprise/agentApplication/middleware/selectAgentApplication'

describe('Agent application routes', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  test('uses the application ID route and standard selection middleware', () => {
    const route = testApp.nuxtApp.$router.resolve({
      name: 'agent-application',
      params: { agentId: 10 },
    })
    expect(route.path).toBe('/agent/10')
    expect(route.meta.middleware).toContain('selectAgentApplication')
  })

  test('rejects application IDs belonging to a different type', async () => {
    await testApp.store.dispatch('application/forceCreate', {
      id: 10,
      name: 'Database',
      type: 'database',
      tables: [],
      workspace: { id: 1 },
    })
    await expect(
      selectAgentApplication(testApp.nuxtApp, { params: { agentId: '10' } })
    ).rejects.toMatchObject({ statusCode: 404 })
    expect(testApp.mock.history.get).toHaveLength(0)
  })

  test.each([true, false])(
    'selects only an authorized application with read access=%s',
    async (allowed) => {
      await testApp.store.dispatch('workspace/forceCreate', {
        id: 1,
        name: 'Workspace',
      })
      await testApp.store.dispatch('application/forceCreate', {
        id: 10,
        name: 'Support agent',
        type: 'agent',
        workspace: { id: 1 },
      })
      testApp.mock.onGet('/workspaces/1/permissions/').reply(200, [])
      const selection = selectAgentApplication(
        { $store: testApp.store, $hasPermission: () => allowed },
        { params: { agentId: '10' } }
      )
      if (allowed) {
        await selection
        expect(testApp.store.getters['application/getSelected'].id).toBe(10)
        expect(testApp.store.getters['workspace/getSelected'].id).toBe(1)
      } else {
        await expect(selection).rejects.toMatchObject({ statusCode: 404 })
        expect(testApp.store.getters['application/getSelected']).toBeNull()
      }
      expect(
        testApp.mock.history.get.some(({ url }) =>
          url.includes('agent-builder')
        )
      ).toBe(false)
    }
  )
})
