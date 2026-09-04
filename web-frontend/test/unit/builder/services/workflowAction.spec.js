import { describe, expect, test, vi } from 'vitest'

import WorkflowActionService from '@baserow/modules/builder/services/workflowAction'

describe('WorkflowActionService', () => {
  test('dispatch uses the builder preview namespace in preview mode', async () => {
    const client = { post: vi.fn().mockResolvedValue({ data: {} }) }

    await WorkflowActionService(client).dispatch(42, { form: {} }, {}, 123)

    expect(client.post).toHaveBeenCalledOnce()
    expect(client.post.mock.calls[0][0]).toBe(
      'builder/preview/123/workflow-actions/42/dispatch/'
    )
    expect(client.post.mock.calls[0][1].get('metadata')).toBe(
      JSON.stringify({ form: {} })
    )
    expect(client.post.mock.calls[0][2]).toEqual({
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  })
})
