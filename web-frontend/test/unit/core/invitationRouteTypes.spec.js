import { describe, expect, test, vi } from 'vitest'

import { LinkInvitationRouteType } from '@baserow/modules/core/invitationRouteTypes'

describe('LinkInvitationRouteType', () => {
  test('is only enabled behind the RBAC_IMPROVEMENTS feature flag', () => {
    const featureFlagIsEnabled = vi.fn().mockReturnValue(false)
    const routeType = new LinkInvitationRouteType({
      app: { $featureFlagIsEnabled: featureFlagIsEnabled },
    })
    const workspace = { id: 42 }

    expect(routeType.isEnabled(workspace)).toBe(false)
    expect(featureFlagIsEnabled).toHaveBeenCalledWith('rbac_improvements')

    featureFlagIsEnabled.mockReturnValue(true)
    expect(routeType.isEnabled(workspace)).toBe(true)
  })
})
