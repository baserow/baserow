import axios from 'axios'
import MockAdapter from 'axios-mock-adapter'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { createStore } from 'vuex'

import dashboardApplicationStore from '@baserow/modules/dashboard/store/dashboardApplication'

describe('dashboardApplication store', () => {
  let client = null
  let mock = null
  let store = null

  const dashboard = { id: 10 }

  const createDashboardStore = () => {
    const vuexStore = createStore({
      modules: {
        dashboardApplication: dashboardApplicationStore,
      },
    })
    vuexStore.$client = client
    return vuexStore
  }

  const seedWidgets = () => {
    store.commit('dashboardApplication/ADD_WIDGET', {
      id: 1,
      order: 1,
      type: 'summary',
    })
    store.commit('dashboardApplication/ADD_WIDGET', {
      id: 2,
      order: 2,
      type: 'summary',
    })
  }

  const orderedWidgetIds = () =>
    store.getters['dashboardApplication/getWidgets'].map((widget) => widget.id)

  beforeEach(() => {
    client = axios.create()
    mock = new MockAdapter(client, { onNoMatch: 'throwException' })
    store = createDashboardStore()
    seedWidgets()
  })

  afterEach(() => {
    mock.restore()
  })

  test('orderWidgets optimistically reorders widgets and persists the new order', async () => {
    let requestData = null
    mock.onPost('/dashboard/10/widgets/order/').replyOnce((config) => {
      requestData = JSON.parse(config.data)
      return [204]
    })

    await store.dispatch('dashboardApplication/orderWidgets', {
      dashboard,
      order: [2, 1],
      oldOrder: [1, 2],
    })

    expect(requestData).toEqual({ widget_ids: [2, 1] })
    expect(orderedWidgetIds()).toEqual([2, 1])
  })

  test('orderWidgets rolls back when the API request fails', async () => {
    mock.onPost('/dashboard/10/widgets/order/').replyOnce(500)

    await expect(
      store.dispatch('dashboardApplication/orderWidgets', {
        dashboard,
        order: [2, 1],
        oldOrder: [1, 2],
      })
    ).rejects.toBeTruthy()

    expect(orderedWidgetIds()).toEqual([1, 2])
  })

  test('handleWidgetsReordered applies realtime order updates', async () => {
    await store.dispatch('dashboardApplication/handleWidgetsReordered', [2, 1])

    expect(orderedWidgetIds()).toEqual([2, 1])
  })
})
