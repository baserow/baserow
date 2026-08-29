import {
  getInitialWorkspaceToolSelection,
  buildWorkspaceToolsSavePayload,
} from '@baserow_enterprise/utils/agentWorkspaceTools'

const TOOLS = [
  { name: 'list_workspaces', group: 'core', is_write: false },
  { name: 'list_rows', group: 'database', is_write: false },
  { name: 'load_row_tools', group: 'database', is_write: true },
  { name: 'create_table', group: 'database', is_write: true },
  { name: 'search_user_docs', group: 'search_user_docs', is_write: false },
]

describe('getInitialWorkspaceToolSelection', () => {
  test('an explicit enabled_tools list wins, dropping unknown names', () => {
    expect(
      getInitialWorkspaceToolSelection(
        { mode: 'read_only', enabled_tools: ['list_rows', 'gone_tool'] },
        TOOLS
      )
    ).toEqual(['list_rows'])
  })

  test('an empty enabled_tools list selects nothing', () => {
    expect(
      getInitialWorkspaceToolSelection({ enabled_tools: [] }, TOOLS)
    ).toEqual([])
  })

  test('no enabled_tools in read_write mode selects everything', () => {
    expect(
      getInitialWorkspaceToolSelection({ mode: 'read_write' }, TOOLS)
    ).toEqual(TOOLS.map((tool) => tool.name))
    expect(getInitialWorkspaceToolSelection(undefined, TOOLS)).toEqual(
      TOOLS.map((tool) => tool.name)
    )
  })

  test('null enabled_tools in read_only mode selects the read tools', () => {
    expect(
      getInitialWorkspaceToolSelection(
        { mode: 'read_only', enabled_tools: null },
        TOOLS
      )
    ).toEqual(['list_workspaces', 'list_rows', 'search_user_docs'])
  })
})

describe('buildWorkspaceToolsSavePayload', () => {
  test('everything checked saves null so future tools are included', () => {
    expect(
      buildWorkspaceToolsSavePayload(
        TOOLS.map((tool) => tool.name),
        TOOLS
      )
    ).toEqual({ enabled_tools: null, mode: 'read_write' })
  })

  test('a partial selection with a write tool saves the list in read_write', () => {
    expect(
      buildWorkspaceToolsSavePayload(['load_row_tools', 'list_rows'], TOOLS)
    ).toEqual({
      // The list follows the universe order, not the click order.
      enabled_tools: ['list_rows', 'load_row_tools'],
      mode: 'read_write',
    })
  })

  test('a selection of only read tools derives read_only mode', () => {
    expect(
      buildWorkspaceToolsSavePayload(['list_rows', 'list_workspaces'], TOOLS)
    ).toEqual({
      enabled_tools: ['list_workspaces', 'list_rows'],
      mode: 'read_only',
    })
  })

  test('an empty selection saves an empty list in read_only mode', () => {
    expect(buildWorkspaceToolsSavePayload([], TOOLS)).toEqual({
      enabled_tools: [],
      mode: 'read_only',
    })
  })
})
