import MockAdapter from 'axios-mock-adapter'

describe('elementContent store', () => {
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

  test('paginates preview collection content through the builder-scoped URL', async () => {
    const builder = { id: 123, _: { selected: false } }
    const page = { id: 42 }
    const element = {
      id: 10,
      _: {
        content: [],
        contentLoading: false,
        hasNextPage: true,
      },
    }
    const dataSource = { id: 2, type: 'local_baserow_list_rows' }
    store.commit('application/SET_ITEMS', [builder])
    store.commit('application/SET_SELECTED', builder)
    await store.dispatch('publicBuilder/setPageMode', 'preview')
    mock.onPost('builder/preview/123/data-sources/2/dispatch/').replyOnce(200, {
      has_next_page: false,
      results: [{ id: 1, Name: 'Ada' }],
    })

    await store.dispatch('elementContent/fetchElementContent', {
      page,
      element,
      dataSource,
      range: [0, 5],
      data: { data_source: { element: element.id } },
      mode: 'preview',
    })

    expect(mock.history.post).toHaveLength(1)
    expect(mock.history.post[0].url).toBe(
      'builder/preview/123/data-sources/2/dispatch/'
    )
    expect(Object.fromEntries(mock.history.post[0].params.entries())).toEqual({
      offset: '0',
      count: '5',
    })
    expect(JSON.parse(mock.history.post[0].data)).toEqual({
      metadata: { data_source: { element: element.id } },
    })
  })
})
