import { describe, expect, test, vi } from 'vitest'
import { AgentBuilderSearchType } from '@baserow_enterprise/agentBuilder/searchTypes'
import { AgentBuilderApplicationType } from '@baserow_enterprise/agentBuilder/applicationTypes'
import { searchTypeRegistry } from '@baserow/modules/core/search/types/registry'

describe('Agent Builder search', () => {
  const application = {
    id: 10,
    type: 'agent_builder',
    workspace: { id: 1 },
    agents: [],
  }

  function makeSearchType(
    enabled = true,
    allowed = true,
    resultApplication = application
  ) {
    const app = {
      $i18n: { t: (key) => key },
      $featureFlagIsEnabled: () => enabled,
      $hasPermission: () => allowed,
      $store: {
        getters: {
          'application/get': (id) =>
            id === 10 ? resultApplication : undefined,
        },
        dispatch: vi.fn(),
      },
      $router: { push: vi.fn() },
    }
    const applicationType = new AgentBuilderApplicationType({ app })
    app.$registry = { get: () => applicationType }
    return { type: new AgentBuilderSearchType({ app }), app }
  }

  test('registers the application search type', () => {
    expect(searchTypeRegistry.get('agent_builder')).toBeInstanceOf(
      AgentBuilderSearchType
    )
  })

  test('opens an empty application using either ID representation', () => {
    const { type } = makeSearchType()
    for (const result of [
      { id: '10' },
      { id: 'other', metadata: { application_id: 10 } },
    ]) {
      expect(type.isNavigable(result)).toBe(true)
      expect(type.buildUrl(result)).toEqual({
        name: 'agent-builder',
        params: { agentBuilderId: 10 },
      })
    }
  })

  test.each([
    [false, true],
    [true, false],
  ])('honors feature enabled=%s and list permission=%s', (enabled, allowed) => {
    const { type, app } = makeSearchType(enabled, allowed)
    expect(type.buildUrl({ id: 10 })).toBeNull()
    expect(type.isNavigable({ id: 10 })).toBe(false)
    expect(type.focusInSidebar({ id: 10 })).toBe(false)
    expect(app.$store.dispatch).not.toHaveBeenCalled()
    expect(app.$router.push).not.toHaveBeenCalled()
  })

  test('rejects missing applications and IDs belonging to other types', () => {
    const { type } = makeSearchType()
    expect(type.buildUrl({ id: 99 })).toBeNull()
    expect(type.buildUrl({ id: 'invalid' })).toBeNull()
    const other = makeSearchType(true, true, {
      ...application,
      type: 'database',
    })
    expect(other.type.buildUrl({ id: 10 })).toBeNull()
  })
})
