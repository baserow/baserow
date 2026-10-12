import { describe, expect, test, vi } from 'vitest'
import { AgentApplicationType } from '@baserow_enterprise/agentApplication/applicationTypes'
import {
  EnterpriseAdminRoleType,
  EnterpriseBuilderRoleType,
} from '@baserow_enterprise/roleTypes'

describe('Agent application type', () => {
  const application = { id: 10, type: 'agent', workspace: { id: 1 } }

  function makeType(enabled, allowed = true) {
    const app = {
      $i18n: { t: (key) => key },
      $featureFlagIsEnabled: vi.fn().mockReturnValue(enabled),
      $hasPermission: vi.fn().mockReturnValue(allowed),
      $router: { push: vi.fn() },
    }
    return { type: new AgentApplicationType({ app }), app }
  }

  test('keeps the stored type available while the feature is disabled', async () => {
    const { type, app } = makeType(false)
    expect(type.getType()).toBe('agent')
    expect(type.canBeCreated()).toBe(false)
    expect(type.isVisible(application)).toBe(false)
    expect(await type.select(application)).toBe(false)
    expect(app.$router.push).not.toHaveBeenCalled()
    expect(app.$featureFlagIsEnabled).toHaveBeenCalledWith('agent-builder')
  })

  test('requires application read permission before opening the agent', async () => {
    const { type, app } = makeType(true, false)
    expect(type.canBeCreated()).toBe(true)
    expect(type.isVisible(application)).toBe(false)
    expect(await type.select(application)).toBe(false)
    expect(app.$hasPermission).toHaveBeenCalledWith(
      'application.read',
      application,
      1
    )
  })

  test('opens the agent using the application ID', async () => {
    const { type, app } = makeType(true)
    expect(await type.select(application)).toBe(true)
    expect(app.$router.push).toHaveBeenCalledWith({
      name: 'agent-application',
      params: { agentId: application.id },
    })
    expect(type.populate(application)).toEqual(application)
    expect(type.getDependents(application)).toEqual([])
  })

  test('assigns administrative roles at application scope', () => {
    const { app } = makeType(true)
    for (const RoleType of [
      EnterpriseAdminRoleType,
      EnterpriseBuilderRoleType,
    ]) {
      expect(new RoleType({ app }).allowedScopeTypes).toContain('application')
      expect(new RoleType({ app }).allowedScopeTypes).not.toContain(
        'agent_builder_agent'
      )
    }
  })
})
