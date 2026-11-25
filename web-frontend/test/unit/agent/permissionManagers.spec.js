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

  test('decides granted operations per agent and only refuses the others', () => {
    const manager = testApp
      .getRegistry()
      .get('permissionManager', 'agent_participation')
    const APPROVE = 'agent_application.approve_tool_calls'
    const permissions = {
      allowed: { [CONTINUE]: [10] },
      denied: { [APPROVE]: [10] },
    }
    const check = (operation, id) =>
      manager.hasPermission(permissions, operation, { id }, 1)

    expect([check(CONTINUE, 10), check(CONTINUE, 11)]).toEqual([true, false])
    expect([check(APPROVE, 10), check(APPROVE, 11)]).toEqual([false, null])
  })
})
