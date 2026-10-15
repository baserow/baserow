import { describe, expect, test, vi } from 'vitest'
import { AgentApplicationSearchType } from '@baserow_enterprise/agent/searchTypes'
import { AgentApplicationType } from '@baserow_enterprise/agent/applicationTypes'
import { searchTypeRegistry } from '@baserow/modules/core/search/types/registry'

describe('Agent application search', () => {
  const application = { id: 10, type: 'agent', workspace: { id: 1 } }

  function makeSearchType(allowed = true, resultApplication = application) {
    const app = {
      $i18n: { t: (key) => key },
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
    const applicationType = new AgentApplicationType({ app })
    app.$registry = { get: () => applicationType }
    return { type: new AgentApplicationSearchType({ app }), app }
  }

  test('registers the application search type', () => {
    expect(searchTypeRegistry.get('agent')).toBeInstanceOf(
      AgentApplicationSearchType
    )
  })

  test('opens the agent application using either ID representation', () => {
    const { type } = makeSearchType()
    for (const result of [
      { id: '10' },
      { id: 'other', metadata: { application_id: 10 } },
    ]) {
      expect(type.isNavigable(result)).toBe(true)
      expect(type.buildUrl(result)).toEqual({
        name: 'agent-application',
        params: { agentId: 10 },
      })
    }
  })

  test('requires application read permission', () => {
    const { type, app } = makeSearchType(false)
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
    const other = makeSearchType(true, {
      ...application,
      type: 'database',
    })
    expect(other.type.buildUrl({ id: 10 })).toBeNull()
  })
})
