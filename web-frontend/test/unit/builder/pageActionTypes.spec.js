import { vi } from 'vitest'

import { PreviewPageActionType } from '@baserow/modules/builder/pageActionTypes'

const page = {
  path: '/products/:id',
  path_params: [{ name: 'id' }],
  query_params: [],
  parameters: { id: 42 },
}

const makeDeferred = () => {
  let resolve
  const promise = new Promise((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

describe('PreviewPageActionType', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  test('opens a tab synchronously before requesting the preview grant', async () => {
    const grant = makeDeferred()
    const client = { post: vi.fn(() => grant.promise) }
    const previewWindow = {
      close: vi.fn(),
      closed: false,
      location: { replace: vi.fn() },
      opener: window,
    }
    const open = vi.spyOn(window, 'open').mockReturnValue(previewWindow)
    const action = new PreviewPageActionType({ app: { $client: client } })

    const clickPromise = action.onClick({ builder: { id: 7 }, page })

    expect(open).toHaveBeenCalledWith('', '_blank')
    expect(previewWindow.opener).toBeNull()
    expect(previewWindow.location.replace).not.toHaveBeenCalled()

    grant.resolve({ data: { url: 'https://preview.example.com/grant' } })
    await clickPromise

    expect(client.post).toHaveBeenCalledWith('builder/preview/7/grant/', {
      path: '/products/42',
    })
    expect(previewWindow.location.replace).toHaveBeenCalledWith(
      'https://preview.example.com/grant'
    )
  })

  test('closes the synchronously opened tab when grant creation fails', async () => {
    const error = new Error('Grant creation failed')
    const client = { post: vi.fn().mockRejectedValue(error) }
    const previewWindow = {
      close: vi.fn(),
      closed: false,
      location: { replace: vi.fn() },
      opener: window,
    }
    vi.spyOn(window, 'open').mockReturnValue(previewWindow)
    const action = new PreviewPageActionType({ app: { $client: client } })

    await expect(action.onClick({ builder: { id: 7 }, page })).rejects.toBe(
      error
    )

    expect(previewWindow.close).toHaveBeenCalledOnce()
    expect(previewWindow.location.replace).not.toHaveBeenCalled()
  })
})
