import { describe, test, expect } from 'vitest'
import { getToolActions } from '@baserow_enterprise/utils/agentToolActions'

const t = (key, params = {}) => `${key}${params.name ? `:${params.name}` : ''}`
const applications = [
  { id: 5, type: 'database', tables: [{ id: 12 }, { id: 13 }] },
  { id: 6, type: 'builder' },
]
const ok = (content) => ({ status: 'ok', content })

describe('getToolActions', () => {
  test('a single created row links to the row', () => {
    const actions = getToolActions({
      toolName: 'create_rows_in_table_12',
      args: { rows: [{}] },
      result: ok({ created_row_ids: [77] }),
      applications,
      t,
    })
    expect(actions).toEqual([
      {
        key: 'row-12-77',
        label: 'agentToolActions.viewRow',
        to: {
          name: 'database-table-row',
          params: { databaseId: 5, tableId: 12, rowId: 77 },
        },
      },
    ])
  })

  test('several rows, deletions and field changes open the table', () => {
    const many = getToolActions({
      toolName: 'update_rows_in_table_13',
      args: {},
      result: ok({ updated_row_ids: [1, 2] }),
      applications,
      t,
    })
    expect(many[0].to).toEqual({
      name: 'database-table',
      params: { databaseId: 5, tableId: 13 },
    })
    const fields = getToolActions({
      toolName: 'create_fields',
      args: { table_id: 12 },
      result: ok({ created_fields: [] }),
      applications,
      t,
    })
    expect(fields[0].label).toBe('agentToolActions.openTable')
  })

  test('created tables and views are listed by name', () => {
    const tables = getToolActions({
      toolName: 'create_tables',
      args: {},
      result: ok({ created_tables: [{ id: 13, name: 'Leads' }] }),
      applications,
      t,
    })
    expect(tables[0].label).toBe('agentToolActions.openNamedTable:Leads')
    const views = getToolActions({
      toolName: 'create_views',
      args: { table_id: 12 },
      result: ok({ created_views: [{ id: 9, name: 'Board' }] }),
      applications,
      t,
    })
    expect(views[0].to.params).toEqual({
      databaseId: 5,
      tableId: 12,
      viewId: 9,
    })
  })

  test('no action for errors, pending calls or unknown tables', () => {
    expect(
      getToolActions({
        toolName: 'create_rows_in_table_12',
        args: {},
        result: { status: 'error', content: 'boom' },
        applications,
        t,
      })
    ).toEqual([])
    expect(
      getToolActions({
        toolName: 'create_rows_in_table_12',
        args: {},
        result: null,
        applications,
        t,
      })
    ).toEqual([])
    expect(
      getToolActions({
        toolName: 'create_rows_in_table_99',
        args: {},
        result: ok({ created_row_ids: [1] }),
        applications,
        t,
      })
    ).toEqual([])
  })
})
