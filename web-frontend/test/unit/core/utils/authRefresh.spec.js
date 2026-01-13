import { makeRefreshAuthInterceptor } from '@baserow/modules/core/plugins/clientAuthRefresh'

describe('test stub interceptors', () => {
  const stubClient = (operations = []) => {
    return {
      interceptors: {
        request: {
          use: vi.fn(() => {
            operations.push('request.use')
          }),
        },
        response: {
          use: vi.fn(() => {
            operations.push('response.use')
          }),
        },
      },
    }
  }

  const refreshAuthMock = (operations) =>
    vi.fn(() => {
      operations.push('promise.created')
      return new Promise((resolve) => {
        operations.push('promise.resolved')
        resolve(42)
      })
    })

  const onRetryMock = (operations) =>
    vi.fn(() => {
      operations.push('retry')
    })

  test('should use correctly requests and response interceptors', async () => {
    const operations = []
    const client = stubClient(operations)

    const refreshMock = refreshAuthMock(operations)
    const retryMock = onRetryMock(operations)
    const refreshAuthInterceptor = makeRefreshAuthInterceptor(
      client,
      refreshMock,
      () => true,
      (error) => error.response.status === 401,
      retryMock
    )

    const refreshAuthPromise = refreshAuthInterceptor({
      response: { status: 401 },
      config: { url: 'some-protected-url' },
    })

    expect(client.interceptors.request.use).toBeCalledTimes(1)
    expect(refreshMock).toBeCalledTimes(1)
    expect(retryMock).toBeCalledTimes(0)

    await refreshAuthPromise
    expect(retryMock).toBeCalledWith({
      url: 'some-protected-url',
      skipAuthRefresh: true,
    })
    expect(operations).toEqual([
      'request.use',
      'promise.created',
      'promise.resolved',
      'retry',
    ])

    operations.length = 0
    const refreshAuthPromise2 = refreshAuthInterceptor({
      response: { status: 401 },
      config: { url: 'some-other-protected-url' },
    })
    const refreshAuthPromise3 = refreshAuthInterceptor({
      response: { status: 401 },
      config: { url: 'yet-other-protected-url' },
    })
    expect(operations).toEqual(['promise.created', 'promise.resolved'])

    await Promise.all([refreshAuthPromise2, refreshAuthPromise3])

    expect(operations).toEqual([
      'promise.created',
      'promise.resolved',
      'retry',
      'retry',
    ])
  })

  test('should not intercept different errors', async () => {
    const operations = []
    const client = stubClient(operations)
    const refreshMock = refreshAuthMock(operations)
    const retryMock = onRetryMock(operations)
    const refreshAuthInterceptor = makeRefreshAuthInterceptor(
      client,
      refreshMock,
      () => true,
      (error) => error.response.status === 401,
      retryMock
    )
    expect(client.interceptors.request.use).toBeCalledTimes(1)

    try {
      await refreshAuthInterceptor({
        response: { status: 404 },
        config: { url: 'some-not-found-url' },
      })
    } catch (error) {
      expect(error).toEqual({
        response: { status: 404 },
        config: { url: 'some-not-found-url' },
      })
    }

    expect(client.interceptors.request.use).toBeCalledTimes(1)
    expect(retryMock).toBeCalledTimes(0)
  })
})
