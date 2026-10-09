import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import { requireAgentBuilderEnabled } from '@baserow_enterprise/agentBuilder/middleware/agentBuilderEnabled'
import { selectAgentBuilder } from '@baserow_enterprise/agentBuilder/middleware/selectAgentBuilder'

describe('Agent Builder routes', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('denies direct routes when the feature flag is disabled', () => {
    expect(() =>
      requireAgentBuilderEnabled({ $featureFlagIsEnabled: () => false })
    ).toThrow('Agent Builder not found')
    expect(testApp.mock.history.get).toHaveLength(0)
    expect(testApp.$registry.get('application', 'agent_builder')).toBeDefined()
    const route = testApp.nuxtApp.$router.resolve({
      name: 'agent-builder',
      params: { agentBuilderId: 10 },
    })
    expect(route.meta.middleware).toContain('agentBuilderEnabled')
    expect(route.meta.middleware).toContain('selectAgentBuilder')
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
      selectAgentBuilder(testApp.nuxtApp, { params: { agentBuilderId: '10' } })
    ).rejects.toMatchObject({ statusCode: 404 })
    expect(testApp.mock.history.get).toHaveLength(0)
  })
})
