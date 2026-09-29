import { describe, expect, test, vi } from 'vitest'

import { AgentsWorkspaceSettingsPageType } from '@baserow/modules/core/workspaceSettingsPageTypes'

describe('AgentsWorkspaceSettingsPageType', () => {
  test('is only visible when the feature flag and permission are enabled', () => {
    const featureFlagIsEnabled = vi.fn().mockReturnValue(false)
    const hasPermission = vi.fn().mockReturnValue(true)
    const pageType = new AgentsWorkspaceSettingsPageType({
      app: {
        $featureFlagIsEnabled: featureFlagIsEnabled,
        $hasPermission: hasPermission,
      },
    })
    const workspace = { id: 42 }

    expect(pageType.hasPermission(workspace)).toBe(false)
    expect(featureFlagIsEnabled).toHaveBeenCalledWith('agents')
    expect(hasPermission).not.toHaveBeenCalled()

    featureFlagIsEnabled.mockReturnValue(true)
    expect(pageType.hasPermission(workspace)).toBe(true)
    expect(hasPermission).toHaveBeenCalledWith(
      'workspace.list_agents',
      workspace,
      workspace.id
    )
  })
})
