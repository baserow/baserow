import { describe, expect, test, vi } from 'vitest'
import { AgentApplicationType } from '@baserow/modules/agent/applicationTypes'
import { AgentLastViewedItemType } from '@baserow/modules/agent/lastViewedItemTypes'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import AgentCreateModal from '@baserow/modules/agent/components/AgentCreateModal'
import CreateApplicationModal from '@baserow/modules/core/components/application/CreateApplicationModal'

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

  test.each([true, false])(
    'offers the recently viewed filter only while the rollout flag is enabled=%s',
    (enabled) => {
      const { type, app } = makeType({ flagEnabled: enabled })
      app.$i18n = { t: (key) => key }
      app.$registry = { get: () => type }
      const lastViewedType = new AgentLastViewedItemType({ app })

      expect(
        lastViewedType.getFilterOptions().map(({ value }) => value)
      ).toEqual(enabled ? ['agent'] : [])
    }
  )

  test('creates agents with the setup wizard and others with the core modal', () => {
    expect(makeType().type.getCreateModalComponent()).toBe(AgentCreateModal)
    expect(
      new DatabaseApplicationType({ app: {} }).getCreateModalComponent()
    ).toBe(CreateApplicationModal)
  })

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
