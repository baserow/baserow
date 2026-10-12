import { describe, expect, test, vi } from 'vitest'

import {
  EmailInvitationRouteType,
  LinkInvitationRouteType,
} from '@baserow/modules/core/invitationRouteTypes'

describe('LinkInvitationRouteType', () => {
  test('is only enabled behind the RBAC_IMPROVEMENTS feature flag', () => {
    const featureFlagIsEnabled = vi.fn().mockReturnValue(false)
    const routeType = new LinkInvitationRouteType({
      app: { $featureFlagIsEnabled: featureFlagIsEnabled },
    })
    const workspace = { id: 42 }
    const workspaceTarget = { type: 'workspace' }

    expect(routeType.isEnabled(workspace, workspaceTarget)).toBe(false)
    expect(featureFlagIsEnabled).toHaveBeenCalledWith('rbac_improvements')

    featureFlagIsEnabled.mockReturnValue(true)
    expect(routeType.isEnabled(workspace, workspaceTarget)).toBe(true)
    expect(routeType.isEnabled(workspace, { type: 'scope' })).toBe(true)
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
