import { vi } from 'vitest'
import WorkflowActionService from '@baserow/modules/database/services/workflowAction'

describe('workflowAction service', () => {
  let client = null
  let service = null

  beforeEach(() => {
    client = {
      get: vi.fn(() => Promise.resolve()),
      post: vi.fn(() => Promise.resolve()),
      patch: vi.fn(() => Promise.resolve()),
      delete: vi.fn(() => Promise.resolve()),
    }
    service = WorkflowActionService(client)
  })

  test('fetchAll targets the field', () => {
    service.fetchAll(11)
    expect(client.get).toHaveBeenCalledWith(
      'database/field/11/workflow_actions/'
    )
  })

  const group = { headers: { ClientUndoRedoActionGroupId: 'group-1' } }

  test('create sends the values it is given', () => {
    service.create(11, {
      type: 'local_baserow_create_row',
      service: { table_id: 3 },
    })
    expect(client.post).toHaveBeenCalledWith(
      'database/field/11/workflow_actions/',
      { type: 'local_baserow_create_row', service: { table_id: 3 } },
      { params: {} }
    )
  })

  test('update targets the action', () => {
    service.update(22, { service: { table_id: 3 } })
    expect(client.patch).toHaveBeenCalledWith(
      'database/workflow_action/22/',
      { service: { table_id: 3 } },
      { params: {} }
    )
  })

  test('delete targets the action', () => {
    service.delete(22)
    expect(client.delete).toHaveBeenCalledWith('database/workflow_action/22/', {
      params: {},
    })
  })

  test('order sends the id list', () => {
    service.order(11, [22, 21])
    expect(client.post).toHaveBeenCalledWith(
      'database/field/11/workflow_actions/order/',
      { workflow_action_ids: [22, 21] },
      { params: {} }
    )
  })

  test('every configuration call sends the undo group it is given', () => {
    service.create(11, {}, 'group-1')
    service.update(22, {}, 'group-1')
    service.delete(22, 'group-1')
    service.order(11, [22], 'group-1')

    expect(client.post.mock.calls[0][2]).toMatchObject(group)
    expect(client.patch.mock.calls[0][2]).toMatchObject(group)
    expect(client.delete.mock.calls[0][1]).toMatchObject(group)
    expect(client.post.mock.calls[1][2]).toMatchObject(group)
  })

  test('dispatch sends the row id', () => {
    service.dispatch(11, 5)
    expect(client.post).toHaveBeenCalledWith(
      'database/field/11/workflow_actions/dispatch/',
      { row_id: 5 },
      // Without this the realtime layer leaves the clicking session out of
      // the broadcast, and their grid stays stale until a reload.
      { omitWebSocketId: true }
    )
  })
})
