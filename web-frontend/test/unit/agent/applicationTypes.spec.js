import { describe, expect, test, vi } from 'vitest'
import { AgentApplicationType } from '@baserow/modules/agent/applicationTypes'

describe('AgentApplicationType', () => {
  const agent = { id: 10, type: 'agent', workspace: { id: 1 } }

  function makeType({ flagEnabled = true, selected = false } = {}) {
    const app = {
      $featureFlagIsEnabled: (flag) => flagEnabled && flag === 'agent-builder',
      $router: { push: vi.fn() },
      $store: { getters: { 'application/isSelected': () => selected } },
    }
    return { type: new AgentApplicationType({ app }), app }
  }

  test.each([true, false])(
    'can be created only while the rollout flag is enabled=%s',
    (enabled) => {
      expect(makeType({ flagEnabled: enabled }).type.canBeCreated()).toBe(
        enabled
      )
    }
  )

  test('opens the agent route by application ID', async () => {
    const { type, app } = makeType()

    expect(await type.select(agent)).toBe(true)
    expect(app.$router.push).toHaveBeenCalledWith({
      name: 'agent-application',
      params: { agentId: 10 },
    })
  })

  test.each([true, false])(
    'returns to the workspace when the deleted agent is selected=%s',
    (selected) => {
      const { type, app } = makeType({ selected })

      type.delete(agent)

      expect(app.$router.push.mock.calls).toEqual(
        selected ? [[{ name: 'workspace', params: { workspaceId: 1 } }]] : []
      )
    }
  )
})
