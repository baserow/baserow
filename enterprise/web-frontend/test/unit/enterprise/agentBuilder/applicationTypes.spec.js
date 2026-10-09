import { describe, expect, test, vi } from 'vitest'
import { AgentBuilderApplicationType } from '@baserow_enterprise/agentBuilder/applicationTypes'
import {
  EnterpriseAdminRoleType,
  EnterpriseBuilderRoleType,
} from '@baserow_enterprise/roleTypes'

describe('Agent Builder application type', () => {
  const application = { id: 10, workspace: { id: 1 } }

  function makeType(enabled, allowed = true) {
    const app = {
      $i18n: { t: (key) => key },
      $featureFlagIsEnabled: vi.fn().mockReturnValue(enabled),
      $hasPermission: vi.fn().mockReturnValue(allowed),
      $router: { push: vi.fn() },
    }
    return { type: new AgentBuilderApplicationType({ app }), app }
  }

  test('keeps the stored type available while the feature is disabled', async () => {
    const { type, app } = makeType(false)
    expect(type.getType()).toBe('agent_builder')
    expect(type.canBeCreated()).toBe(false)
    expect(type.isVisible(application)).toBe(false)
    expect(await type.select(application)).toBe(false)
    expect(app.$router.push).not.toHaveBeenCalled()
    expect(app.$featureFlagIsEnabled).toHaveBeenCalledWith('agent-builder')
  })

  test('requires list permission before opening the application', async () => {
    const { type, app } = makeType(true, false)
    expect(type.canBeCreated()).toBe(true)
    expect(type.isVisible(application)).toBe(false)
    expect(await type.select(application)).toBe(false)
    expect(app.$hasPermission).toHaveBeenCalledWith(
      'agent_builder.list_agents',
      application,
      1
    )
  })

  test('opens the empty application without assuming a first agent', async () => {
    const { type, app } = makeType(true)
    expect(await type.select(application)).toBe(true)
    expect(app.$router.push).toHaveBeenCalledWith({
      name: 'agent-builder',
      params: { agentBuilderId: application.id },
    })
    expect(type.populate(application).agents).toEqual([])
  })

  test('allows administrative roles to be assigned to child agents', () => {
    const { app } = makeType(true)
    for (const RoleType of [
      EnterpriseAdminRoleType,
      EnterpriseBuilderRoleType,
    ]) {
      expect(new RoleType({ app }).allowedScopeTypes).toContain(
        'agent_builder_agent'
      )
    }
  })
})
