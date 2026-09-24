import { describe, expect, test } from 'vitest'

import { getWorkspaceMembersCount } from '@baserow/modules/core/utils/workspace'

describe('workspace utils', () => {
  const workspace = {
    users: [{ id: 1 }],
    agents_count: 1,
  }

  test('includes agents when they are visible', () => {
    expect(getWorkspaceMembersCount(workspace, true)).toBe(2)
  })

  test('only includes users when agents are not visible', () => {
    expect(getWorkspaceMembersCount(workspace, false)).toBe(1)
  })
})
