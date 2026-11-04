import { describe, expect, test, vi } from 'vitest'

import {
  EmailInvitationRouteType,
  LinkInvitationRouteType,
} from '@baserow/modules/core/invitationRouteTypes'

describe('LinkInvitationRouteType', () => {
  function createRouteType(
    featureFlagIsEnabled,
    settings = {
      allow_new_signups: true,
      allow_signups_via_workspace_invitations: false,
    }
  ) {
    const targetTypes = {
      workspace: { supportsInvitationLinks: () => true },
      scope: { supportsInvitationLinks: () => false },
    }
    return new LinkInvitationRouteType({
      app: {
        $featureFlagIsEnabled: featureFlagIsEnabled,
        $registry: { get: (registry, type) => targetTypes[type] },
        $store: { getters: { 'settings/get': settings } },
      },
    })
  }

  test('is only enabled behind the RBAC_IMPROVEMENTS feature flag', () => {
    const featureFlagIsEnabled = vi.fn().mockReturnValue(false)
    const routeType = createRouteType(featureFlagIsEnabled)
    const workspace = { id: 42 }
    const workspaceTarget = { type: 'workspace' }

    expect(routeType.isEnabled(workspace, workspaceTarget)).toBe(false)
    expect(featureFlagIsEnabled).toHaveBeenCalledWith('rbac_improvements')

    featureFlagIsEnabled.mockReturnValue(true)
    expect(routeType.isEnabled(workspace, workspaceTarget)).toBe(true)
  })

  test('is only enabled while people can sign up through links', () => {
    const featureFlagIsEnabled = vi.fn().mockReturnValue(true)
    const workspace = { id: 42 }
    const target = { type: 'workspace' }
    const enabled = (settings) =>
      createRouteType(featureFlagIsEnabled, settings).isEnabled(
        workspace,
        target
      )

    expect(
      enabled({
        allow_new_signups: true,
        allow_signups_via_workspace_invitations: false,
      })
    ).toBe(true)
    expect(
      enabled({
        allow_new_signups: false,
        allow_signups_via_workspace_invitations: true,
      })
    ).toBe(true)
    expect(
      enabled({
        allow_new_signups: false,
        allow_signups_via_workspace_invitations: false,
      })
    ).toBe(false)
  })

  test('is only enabled for targets that support links', () => {
    const routeType = createRouteType(vi.fn().mockReturnValue(true))
    const workspace = { id: 42 }

    expect(routeType.isEnabled(workspace, { type: 'workspace' })).toBe(true)
    expect(routeType.isEnabled(workspace, { type: 'scope' })).toBe(false)
  })
})

describe('EmailInvitationRouteType', () => {
  test('only serves the workspace target', () => {
    const routeType = new EmailInvitationRouteType({ app: {} })
    const workspace = { id: 42 }

    expect(routeType.isEnabled(workspace, { type: 'workspace' })).toBe(true)
    expect(routeType.isEnabled(workspace, { type: 'scope' })).toBe(false)
  })
})
