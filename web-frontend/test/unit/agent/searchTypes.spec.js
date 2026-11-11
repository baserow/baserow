import { describe, expect, test } from 'vitest'
import { AgentApplicationSearchType } from '@baserow/modules/agent/searchTypes'

describe('AgentApplicationSearchType', () => {
  const searchType = new AgentApplicationSearchType({
    app: { $i18n: { t: (key) => key } },
  })

  test.each([
    ['its id', { id: '10' }],
    ['an id in metadata', { id: 'x', metadata: { application_id: 10 } }],
  ])('opens the agent from %s', (_, result) => {
    expect(searchType.isNavigable(result)).toBe(true)
    expect(searchType.buildUrl(result)).toEqual({
      name: 'agent-application',
      params: { agentId: 10 },
    })
  })

  test('ignores a result without an id', () => {
    expect(searchType.isNavigable({ id: 'x' })).toBe(false)
    expect(searchType.buildUrl({ id: 'x' })).toBeNull()
  })
})
