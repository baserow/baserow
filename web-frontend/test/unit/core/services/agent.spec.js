import { expect, test, vi } from 'vitest'
import AgentService from '@baserow/modules/core/services/agent'

test('lists every Agent page for selectors', async () => {
  const agents = Array.from({ length: 201 }, (_, id) => ({
    id,
    name: `Agent ${id}`,
  }))
  const client = {
    get: vi
      .fn()
      .mockResolvedValueOnce({
        data: { count: 201, next: 'next-page', results: agents.slice(0, 200) },
      })
      .mockResolvedValueOnce({
        data: { count: 201, next: null, results: agents.slice(200) },
      }),
  }
  const { data } = await AgentService(client).list(12)
  expect(data.results).toEqual(agents)
  expect(data.next).toBeNull()
  expect(client.get).toHaveBeenNthCalledWith(2, '/agents/workspace/12/', {
    params: { size: 200, page: 2 },
  })
})

test('does not return partial selector results when another page fails', async () => {
  const error = new Error('Network error')
  const client = {
    get: vi
      .fn()
      .mockResolvedValueOnce({
        data: { next: 'next-page', results: [{ id: 1 }] },
      })
      .mockRejectedValueOnce(error),
  }
  await expect(AgentService(client).list(12)).rejects.toBe(error)
})
