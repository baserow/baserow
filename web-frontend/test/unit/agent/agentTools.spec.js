import { describe, expect, test } from 'vitest'
import {
  agentToolsRequiring,
  nextAskFirst,
  requiredAgentTools,
  usableAgentTools,
} from '@baserow/modules/agent/agentTools'

const availableTools = [
  { name: 'list_tables', changes_data: false },
  { name: 'create_rows', changes_data: true },
  { name: 'delete_rows', changes_data: true },
]

describe('nextAskFirst', () => {
  test.each([
    [
      'newly allowed change tools ask first, reads do not',
      [],
      [],
      ['delete_rows', 'list_tables', 'create_rows'],
      ['create_rows', 'delete_rows'],
    ],
    [
      'tools that stay allowed keep their setting',
      ['list_tables', 'create_rows'],
      ['list_tables'],
      ['list_tables', 'create_rows', 'delete_rows'],
      ['list_tables', 'delete_rows'],
    ],
    [
      'tools that are no longer allowed stop asking',
      ['list_tables', 'create_rows', 'delete_rows'],
      ['create_rows', 'delete_rows'],
      ['list_tables', 'create_rows'],
      ['create_rows'],
    ],
  ])('%s', (_, prevAllowed, prevAskFirst, nextAllowed, expected) => {
    expect(
      nextAskFirst(availableTools, prevAllowed, prevAskFirst, nextAllowed)
    ).toEqual(expected)
  })
})

describe('usableAgentTools', () => {
  test('leaves out the tools the workspace cannot use', () => {
    const locked = { name: 'create_row_comments', deactivated: true }

    expect(usableAgentTools([...availableTools, locked])).toEqual(
      availableTools
    )
  })
})

const toolsWithRequirements = [
  { name: 'list_tables', requires: [] },
  { name: 'get_table_schema', requires: ['list_tables'] },
  { name: 'list_table_rows', requires: ['list_tables'] },
  { name: 'create_rows', requires: ['get_table_schema'] },
  { name: 'update_rows', requires: ['get_table_schema', 'list_table_rows'] },
]

describe('requiredAgentTools', () => {
  test('follows the requirements through other tools', () => {
    expect([
      ...requiredAgentTools(toolsWithRequirements, ['create_rows']),
    ]).toEqual(['get_table_schema', 'list_tables'])
  })
})

describe('agentToolsRequiring', () => {
  test('names every allowed tool that requires each tool', () => {
    const allowed = new Set([
      'list_tables',
      'get_table_schema',
      'list_table_rows',
      'create_rows',
      'update_rows',
    ])
    expect(
      Object.fromEntries(agentToolsRequiring(toolsWithRequirements, allowed))
    ).toEqual({
      list_tables: [
        'get_table_schema',
        'list_table_rows',
        'create_rows',
        'update_rows',
      ],
      get_table_schema: ['create_rows', 'update_rows'],
      list_table_rows: ['update_rows'],
    })
  })
})
