import { expect } from 'vitest'
import { MockServer } from '@baserow/test/fixtures/mockServer'
import MockAdapter from 'axios-mock-adapter'

describe('dataSource store', () => {
  let testApp = null
  let store = null
  let mockServer = null
  let mock = null

  beforeEach(() => {
    testApp = useNuxtApp()
    const { $store, $client, $registry } = useNuxtApp()
    store = $store
    mock = new MockAdapter($client, { onNoMatch: 'throwException' })
    mockServer = new MockServer(mock, $store)
  })

  afterEach(() => {
    mock.restore()
  })

  test('getPageDataSources', () => {
    const page = {
      id: 42,
      dataSources: [
        { type: null },
        { type: 'local_baserow_list_rows' },
        { type: 'local_baserow_get_row' },
      ],
    }

    const collectionDataSources =
      store.getters['dataSource/getPageDataSources'](page)

    expect(collectionDataSources.length).toBe(3)
  })

  test('fetch', async () => {
    const page = {
      id: 42,
      dataSources: [],
      _: {},
    }

    // Mock the fetch call
    mockServer.mock
      .onGet(`builder/page/42/data-sources/`)
      .replyOnce(200, [
        { type: null },
        { type: 'local_baserow_list_rows' },
        { type: 'local_baserow_get_row' },
      ])

    await store.dispatch('dataSource/fetch', {
      page,
    })

    const collectionDataSources =
      store.getters['dataSource/getPageDataSources'](page)

    expect(collectionDataSources.length).toBe(3)
  })
})
