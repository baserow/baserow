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

  test('emits a type change and keeps the position', () => {
    const server = [{ id: 1, type: 'create_row', service: { table_id: 5 } }]
    const local = [{ id: 1, type: 'open_url', url: { formula: "'x'" } }]

    const { toUpdate, order } = reconcileWorkflowActions(server, local)

    expect(toUpdate).toEqual([
      { id: 1, values: { type: 'open_url', url: { formula: "'x'" } } },
    ])
    expect(order).toEqual([1])
  })

  test('a type change between two service types sends the new config', () => {
    const server = [{ id: 1, type: 'create_row', service: { table_id: 3 } }]
    const local = [{ id: 1, type: 'update_row', service: { table_id: 3 } }]

    const result = reconcileWorkflowActions(server, local)

    expect(result.toUpdate).toEqual([
      { id: 1, values: { type: 'update_row', service: { table_id: 3 } } },
    ])
  })

  test('the keys the api owns are never diffed or sent', () => {
    // `order` and `field_id` come back on every action but belong to the
    // server, not to the editor: the order is applied by its own endpoint and
    // the field never changes. Diffing them would make a pure reorder look
    // like a config change and send them straight back.
    const server = [
      { id: 1, type: 'create_row', order: 1, field_id: 7, service: {} },
    ]
    const local = [
      { id: 1, type: 'create_row', order: 9, field_id: 7, service: {} },
    ]

    const result = reconcileWorkflowActions(server, local)

    expect(result.toUpdate).toEqual([])
  })

  test('a row whose type has not been chosen yet is not an action', () => {
    // The picker adds an empty row first and the user chooses its type
    // afterwards. Saving before that must produce no work at all, and no
    // slot in the order.
    const server = [{ id: 1, type: 'create_row', service: {} }]
    const local = [{ id: 1, type: 'create_row', service: {} }, { type: null }]

    const result = reconcileWorkflowActions(server, local)

    expect(result.toCreate).toEqual([])
    expect(result.toUpdate).toEqual([])
    expect(result.toDelete).toEqual([])
    expect(result.order).toEqual([1])
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
