import {
  hasMoreAccess,
  workspaceToolIdentities,
  listToolIdentityExceptions,
} from '@baserow_enterprise/utils/agentToolIdentities'

const investor = { id: 1, name: 'Investor', role_uid: 'BUILDER' }
const outreach = { id: 2, name: 'Baserow Outreach', role_uid: 'EDITOR' }
const admin = { id: 3, name: 'Admin', role_uid: 'ADMIN' }

describe('agentToolIdentities', () => {
  test('flags identities with more access than the agent', () => {
    expect(hasMoreAccess(outreach, investor)).toBe(false)
    expect(hasMoreAccess(admin, investor)).toBe(true)
    expect(hasMoreAccess(outreach, null)).toBe(true)
    expect(hasMoreAccess({ id: 4, role_uid: 'custom' }, investor)).toBe(false)
  })

  test('normalizes the tool identities of a config', () => {
    expect(
      workspaceToolIdentities({ tool_identities: { a: 2, b: '3', c: 'x' } })
    ).toEqual({ a: 2, b: 3 })
    expect(workspaceToolIdentities(undefined)).toEqual({})
  })

  test('lists workspace and action tool exceptions', () => {
    const exceptions = listToolIdentityExceptions({
      workspaceTool: {
        config: { tool_identities: { list_rows: 2, gone: 99 } },
      },
      actionTools: [
        { id: 7, type: 'service', name: 'Send an email', identity_id: 2 },
        { id: 8, type: 'service', name: 'Slack', identity_id: null },
      ],
      catalog: [{ name: 'list_rows', label: 'Read rows' }],
      identities: [investor, outreach],
    })
    expect(
      exceptions.map((item) => [item.key, item.label, item.identity.id])
    ).toEqual([
      ['workspace-list_rows', 'Read rows', 2],
      ['action-7', 'Send an email', 2],
    ])
  })
})
