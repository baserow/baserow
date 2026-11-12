import MockAdapter from 'axios-mock-adapter'
import { vi } from 'vitest'

const reloadNuxtApp = vi.hoisted(() => vi.fn())

vi.mock('#app', async (importOriginal) => ({
  ...(await importOriginal()),
  reloadNuxtApp,
}))

describe('dataSourceContent store', () => {
  let client
  let mock
  let store

  beforeEach(() => {
    const nuxtApp = useNuxtApp()
    client = nuxtApp.$client
    store = nuxtApp.$store
    mock = new MockAdapter(client, { onNoMatch: 'throwException' })
  })

  afterEach(() => {
    mock.restore()
    vi.useRealTimers()
    reloadNuxtApp.mockClear()
  })

  test('dispatches preview content through the builder-scoped URL', async () => {
    const builder = { id: 123, _: { selected: false } }
    const page = { id: 42, _: {}, contents: {} }
    store.commit('application/SET_ITEMS', [builder])
    store.commit('application/SET_SELECTED', builder)
    await store.dispatch('publicBuilder/setPageMode', 'preview')
    mock
      .onPost('builder/preview/123/pages/42/dispatch-data-sources/', {
        metadata: { page_parameter: 'value' },
      })
      .replyOnce(200, {})

    await store.dispatch('dataSourceContent/fetchPageDataSourceContent', {
      page,
      data: { page_parameter: 'value' },
      mode: 'preview',
    })

    expect(mock.history.post).toHaveLength(1)
  })

  test('reloads when a debounced fetch finds the page gone', async () => {
    vi.useFakeTimers()
    const page = { id: 42, _: {}, contents: {} }
    mock.onPost(/pages?\/42\/dispatch-data-sources\/$/).replyOnce(404, {
      error: 'ERROR_PAGE_DOES_NOT_EXIST',
    })

    await store.dispatch(
      'dataSourceContent/debouncedFetchPageDataSourceContent',
      { page, data: {}, mode: 'public' }
    )
    await vi.advanceTimersByTimeAsync(500)

    await vi.waitFor(() =>
      expect(reloadNuxtApp).toHaveBeenCalledWith({
        path: `${window.location.pathname}${window.location.search}`,
        force: true,
      })
    )
    expect(mock.history.post).toHaveLength(1)
  })
})
