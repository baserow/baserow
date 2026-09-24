import MockAdapter from 'axios-mock-adapter'

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
})
