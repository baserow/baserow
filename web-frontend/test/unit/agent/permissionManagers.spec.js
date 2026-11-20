import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'

const CONTINUE = 'agent_application.continue_triggered_conversation'

describe('Agent permission managers', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('refuses continuing a triggered conversation and leaves other operations to the next managers', () => {
    const manager = testApp
      .getRegistry()
      .get('permissionManager', 'agent_triggered_conversations')
    const permissions = { denied_operations: [CONTINUE] }

    expect(manager.hasPermission(permissions, CONTINUE, { id: 10 }, 1)).toBe(
      false
    )
    expect(
      manager.hasPermission(
        permissions,
        'agent_application.approve_tool_calls',
        { id: 10 },
        1
      )
    ).toBeNull()
  })
})
