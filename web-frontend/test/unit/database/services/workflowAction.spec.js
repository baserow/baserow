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

  test('create sends only the type', () => {
    service.create(11, 'create_row')
    expect(client.post).toHaveBeenCalledWith(
      'database/field/11/workflow_actions/',
      { type: 'create_row' }
    )
  })

  test('update targets the action', () => {
    service.update(22, { service: { table_id: 3 } })
    expect(client.patch).toHaveBeenCalledWith('database/workflow_action/22/', {
      service: { table_id: 3 },
    })
  })

  test('delete targets the action', () => {
    service.delete(22)
    expect(client.delete).toHaveBeenCalledWith('database/workflow_action/22/')
  })

  test('order sends the id list', () => {
    service.order(11, [22, 21])
    expect(client.post).toHaveBeenCalledWith(
      'database/field/11/workflow_actions/order/',
      { workflow_action_ids: [22, 21] }
    )
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
