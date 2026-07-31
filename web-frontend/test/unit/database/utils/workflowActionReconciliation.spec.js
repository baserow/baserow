import { reconcileWorkflowActions } from '@baserow/modules/database/utils/workflowActionReconciliation'

describe('reconcileWorkflowActions', () => {
  test('an unchanged list produces no work', () => {
    const server = [{ id: 1, type: 'create_row', service: { table_id: 3 } }]
    const local = [{ id: 1, type: 'create_row', service: { table_id: 3 } }]

    const result = reconcileWorkflowActions(server, local)

    expect(result.toCreate).toEqual([])
    expect(result.toUpdate).toEqual([])
    expect(result.toDelete).toEqual([])
    expect(result.order).toEqual([1])
  })

  test('a new action is created', () => {
    const local = [{ type: 'delete_row', service: { table_id: 4 } }]

    const result = reconcileWorkflowActions([], local)

    expect(result.toCreate).toEqual([
      { type: 'delete_row', service: { table_id: 4 } },
    ])
    expect(result.order).toEqual([null])
  })

  test('a changed service config is updated', () => {
    const server = [{ id: 1, type: 'create_row', service: { table_id: 3 } }]
    const local = [{ id: 1, type: 'create_row', service: { table_id: 9 } }]

    const result = reconcileWorkflowActions(server, local)

    expect(result.toUpdate).toEqual([
      { id: 1, values: { service: { table_id: 9 } } },
    ])
    expect(result.toCreate).toEqual([])
    expect(result.toDelete).toEqual([])
  })

  test('a removed action is deleted', () => {
    const server = [
      { id: 1, type: 'create_row', service: {} },
      { id: 2, type: 'delete_row', service: {} },
    ]
    const local = [{ id: 2, type: 'delete_row', service: {} }]

    const result = reconcileWorkflowActions(server, local)

    expect(result.toDelete).toEqual([1])
    expect(result.order).toEqual([2])
  })

  test('reordering alone produces only an order', () => {
    const server = [
      { id: 1, type: 'create_row', service: {} },
      { id: 2, type: 'delete_row', service: {} },
    ]
    const local = [server[1], server[0]]

    const result = reconcileWorkflowActions(server, local)

    expect(result.toCreate).toEqual([])
    expect(result.toUpdate).toEqual([])
    expect(result.toDelete).toEqual([])
    expect(result.order).toEqual([2, 1])
  })

  test('a mixed edit produces every operation', () => {
    const server = [
      { id: 1, type: 'create_row', service: { table_id: 3 } },
      { id: 2, type: 'delete_row', service: { table_id: 4 } },
    ]
    const local = [
      { id: 2, type: 'delete_row', service: { table_id: 4 } },
      { id: 1, type: 'create_row', service: { table_id: 7 } },
      { type: 'update_row', service: { table_id: 8 } },
    ]

    const result = reconcileWorkflowActions(server, local)

    expect(result.toDelete).toEqual([])
    expect(result.toUpdate).toEqual([
      { id: 1, values: { service: { table_id: 7 } } },
    ])
    expect(result.toCreate).toEqual([
      { type: 'update_row', service: { table_id: 8 } },
    ])
    expect(result.order).toEqual([2, 1, null])
  })

  test('a type change on an existing action is not detected', () => {
    // The editor offers no way to change an existing action's type — you
    // delete and re-add. This test documents that assumption: if a type
    // dropdown is ever added, this test fails and the diff must grow a
    // type comparison.
    const server = [{ id: 1, type: 'create_row', service: { table_id: 3 } }]
    const local = [{ id: 1, type: 'update_row', service: { table_id: 3 } }]

    const result = reconcileWorkflowActions(server, local)

    expect(result.toUpdate).toEqual([])
  })

  test('an id the server does not know is treated as new', () => {
    const local = [{ id: 99, type: 'delete_row', service: { table_id: 4 } }]

    const result = reconcileWorkflowActions([], local)

    expect(result.toUpdate).toEqual([])
    expect(result.toCreate).toEqual([
      { type: 'delete_row', service: { table_id: 4 } },
    ])
    expect(result.order).toEqual([null])
  })
})
