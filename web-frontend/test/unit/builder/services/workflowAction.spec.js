import { describe, expect, test, vi } from 'vitest'

import WorkflowActionService from '@baserow/modules/builder/services/workflowAction'

describe('WorkflowActionService', () => {
  test('dispatch opts into builder preview authentication', async () => {
    const client = { post: vi.fn().mockResolvedValue({ data: {} }) }

    await WorkflowActionService(client).dispatch(42, { form: {} }, {})

    expect(client.post).toHaveBeenCalledOnce()
    expect(client.post.mock.calls[0][0]).toBe(
      'builder/workflow_action/42/dispatch/'
    )
    expect(client.post.mock.calls[0][2]).toEqual({
      usePreviewAuth: true,
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  })
})
