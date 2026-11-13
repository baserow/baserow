import { expect, test, vi } from 'vitest'
import IdentityService from '@baserow/modules/core/services/identity'

test.each([false, true])(
  'lists every identity page with forSelection=%s',
  async (forSelection) => {
    const identities = Array.from({ length: 201 }, (_, id) => ({
      id,
      name: `Identity ${id}`,
    }))
    const client = {
      get: vi
        .fn()
        .mockResolvedValueOnce({
          data: {
            count: 201,
            next: 'next-page',
            results: identities.slice(0, 200),
          },
        })
        .mockResolvedValueOnce({
          data: { count: 201, next: null, results: identities.slice(200) },
        }),
    }
    const { data } = await IdentityService(client).list(12, { forSelection })
    expect(data.results).toEqual(identities)
    expect(data.next).toBeNull()
    expect(client.get).toHaveBeenNthCalledWith(2, '/identities/workspace/12/', {
      params: {
        size: 200,
        page: 2,
        ...(forSelection ? { for_selection: true } : {}),
      },
    })
  }
)

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
  await expect(IdentityService(client).list(12)).rejects.toBe(error)
})

test.each([false, true])(
  'fetches one identity page with forSelection=%s',
  async (forSelection) => {
    const client = { get: vi.fn().mockResolvedValue({ data: { results: [] } }) }
    await IdentityService(client).listPage(12, {
      page: 2,
      search: 'Writer',
      forSelection,
    })
    expect(client.get).toHaveBeenCalledWith('/identities/workspace/12/', {
      params: {
        page: 2,
        size: 100,
        search: 'Writer',
        ...(forSelection ? { for_selection: true } : {}),
      },
    })
  }
)
