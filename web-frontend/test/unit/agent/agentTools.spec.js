import { describe, expect, test } from 'vitest'
import { nextAskFirst } from '@baserow/modules/agent/agentTools'

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
