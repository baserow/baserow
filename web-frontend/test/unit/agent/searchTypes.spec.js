import { describe, expect, test } from 'vitest'
import { AgentApplicationSearchType } from '@baserow/modules/agent/searchTypes'

describe('AgentApplicationSearchType', () => {
  const agent = { id: 10, type: 'agent' }

  function makeSearchType(application, canRead) {
    const app = {
      $i18n: { t: (key) => key },
      $store: {
        getters: {
          'application/get': (id) =>
            id === application.id ? application : undefined,
        },
      },
      $registry: { get: () => ({ isVisible: () => canRead }) },
    }
    return new AgentApplicationSearchType({ app })
  }

  test.each([
    ['a readable agent', agent, true, { id: '10' }, true],
    [
      'an agent ID in metadata',
      agent,
      true,
      { id: 'x', metadata: { application_id: 10 } },
      true,
    ],
    ['an unreadable agent', agent, false, { id: 10 }, false],
    [
      'another application type',
      { id: 10, type: 'database' },
      true,
      { id: 10 },
      false,
    ],
    ['a missing application', agent, true, { id: 99 }, false],
  ])('resolves %s', (_, application, canRead, result, navigable) => {
    const searchType = makeSearchType(application, canRead)

    expect(searchType.isNavigable(result)).toBe(navigable)
    expect(searchType.buildUrl(result)).toEqual(
      navigable ? { name: 'agent-application', params: { agentId: 10 } } : null
    )
  })
})
