import { expect } from 'vitest'
import { MockServer } from '@baserow/test/fixtures/mockServer'
import MockAdapter from 'axios-mock-adapter'
import dataSourceStore from '@baserow/modules/builder/store/dataSource'

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

describe('dataSource redispatchForIntegration', () => {
  const builder = { id: 1 }
  const selectedPage = { id: 10 }
  const sharedPage = { id: 99 }

  const run = (dataSources, integrationId) => {
    const dispatch = vi.fn()
    const element = { id: 100 }
    const rootGetters = {
      'page/getSelected': selectedPage,
      'page/getSharedPage': () => sharedPage,
      'element/getElementsOrdered': (page) =>
        page.id === selectedPage.id ? [element] : [],
    }
    const getters = { getPagesDataSources: () => dataSources }
    dataSourceStore.actions.redispatchForIntegration(
      { dispatch, getters, rootGetters },
      { builder, integrationId }
    )
    return { dispatch, element }
  }

  test('re-dispatches only the data sources bound to the integration', () => {
    const { dispatch, element } = run(
      [
        { id: 1, integration_id: 5 },
        { id: 2, integration_id: 6 },
        { id: 3, integration_id: 5 },
      ],
      5
    )

    const calls = dispatch.mock.calls.filter(
      ([name]) => name === 'element/emitElementEvent'
    )
    expect(calls.map(([, payload]) => payload.dataSourceId)).toEqual([1, 3])
    calls.forEach(([, payload, opts]) => {
      expect(payload.event).toBe('DATA_SOURCE_AFTER_UPDATE')
      expect(payload.elements).toEqual([element])
      expect(payload.builder).toBe(builder)
      expect(opts).toEqual({ root: true })
    })
  })

  test('does nothing when no data source uses the integration', () => {
    const { dispatch } = run([{ id: 1, integration_id: 6 }], 5)
    expect(dispatch).not.toHaveBeenCalled()
  })
})
