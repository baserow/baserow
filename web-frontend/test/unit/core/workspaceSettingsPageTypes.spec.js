import { describe, expect, test, vi } from 'vitest'

import { AgentsWorkspaceSettingsPageType } from '@baserow/modules/core/workspaceSettingsPageTypes'

describe('AgentsWorkspaceSettingsPageType', () => {
  test('is only visible when the permission is enabled', () => {
    const hasPermission = vi.fn().mockReturnValue(true)
    const pageType = new AgentsWorkspaceSettingsPageType({
      app: {
        $hasPermission: hasPermission,
      },
    })
    const workspace = { id: 42 }

    expect(pageType.developmentStage).toBe('beta')
    expect(pageType.hasPermission(workspace)).toBe(true)
    expect(hasPermission).toHaveBeenCalledWith(
      'workspace.list_agents',
      workspace,
      workspace.id
    )

    hasPermission.mockReturnValue(false)
    expect(pageType.hasPermission(workspace)).toBe(false)
  })
})
