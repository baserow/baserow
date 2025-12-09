import { TestApp } from '@baserow/test/helpers/testApp'
import { expect } from 'vitest'

describe('dataSource store', () => {
  let testApp = null
  let store = null
  let mockServer = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
    mockServer = testApp.mockServer
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('Test getPageDataSources', () => {
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

  test('Test fetch', async () => {
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
