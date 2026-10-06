import { describe, expect, test, vi } from 'vitest'
import { AgentApplicationType } from '@baserow_enterprise/agentApplication/applicationTypes'

describe('AgentApplicationType', () => {
  const type = new AgentApplicationType({ app: {} })
  const application = (selected) => ({
    id: 5,
    workspace: { id: 9 },
    _: { selected },
  })

  test('deleting the open agent goes back to the workspace', () => {
    const $router = { push: vi.fn() }
    type.delete(application(true), { $router })
    expect($router.push).toHaveBeenCalledWith({
      name: 'workspace',
      params: { workspaceId: 9 },
    })
  })

  test('deleting another agent leaves the current page alone', () => {
    const $router = { push: vi.fn() }
    type.delete(application(false), { $router })
    expect($router.push).not.toHaveBeenCalled()
  })
})
