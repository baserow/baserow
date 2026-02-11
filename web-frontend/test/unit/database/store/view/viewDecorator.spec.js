// import { TestApp } from '@baserow/test/helpers/testApp'
import { mountSuspended } from '@nuxt/test-utils/runtime'
//import axios from 'axios'

import { MockServer } from '@baserow/test/fixtures/mockServer'
import MockAdapter from 'axios-mock-adapter'

describe('View store - decorator', () => {
  let testApp = null
  let store = null
  let mockServer = null
  let mock = null

  beforeEach(() => {
    //testApp = new TestApp()
    // mockServer = testApp.mockServer
    const { $store, $client: axios } = useNuxtApp()
    store = $store
    mock = new MockAdapter(axios, { onNoMatch: 'throwException' })
    mockServer = new MockServer(mock, $store)
  })

  afterEach(() => {
    mock.restore()
    //testApp.afterEach()
  })

  test('create decoration', async () => {
    const view = {
      id: 42,
      decorations: [],
    }

    mockServer.createDecoration(
      view,
      {
        type: 'left_border_color',
        value_provider_type: 'single_select_color',
      },
      {
        type: 'left_border_color',
        value_provider_type: 'single_select_color',
        value_provider_conf: {},
        order: 1,
        id: 25,
      }
    )

    await store.dispatch('view/createDecoration', {
      view,
      values: {
        type: 'left_border_color',
        value_provider_type: 'single_select_color',
      },
    })

    expect(view.decorations.length).toBe(1)
    expect(view.decorations[0].id).toBeDefined()
    expect(view.decorations[0].type).toBe('left_border_color')
    expect(view.decorations[0].value_provider_type).toBe('single_select_color')
    expect(view.decorations[0]._).toEqual({ loading: false })

    await store.dispatch('view/forceCreateDecoration', {
      view,
      values: {
        type: 'background_color',
        value_provider_type: 'conditional_color',
      },
    })

    expect(view.decorations.length).toBe(2)
    expect(view.decorations[1].type).toBe('background_color')
    expect(view.decorations[1].value_provider_type).toBe('conditional_color')
    expect(view.decorations[1]._).toEqual({ loading: false })
  })

  test('update decoration', async () => {
    const decoration = {
      id: 1,
      type: 'left_border_color',
      value_provider_type: 'single_select_color',
      _: {
        loading: false,
      },
    }
    const view = {
      id: 42,
      decorations: [decoration],
    }

    mockServer.updateDecoration(
      decoration,
      {
        type: 'background_color',
      },
      {
        type: 'left_border_color',
        value_provider_type: 'background_color',
        value_provider_conf: {},
        order: 1,
        id: 1,
      }
    )

    await store.dispatch('view/updateDecoration', {
      view,
      decoration,
      values: {
        type: 'background_color',
      },
    })

    expect(view.decorations.length).toBe(1)
    expect(view.decorations[0].type).toBe('background_color')
    expect(view.decorations[0].value_provider_type).toBe('single_select_color')
    expect(view.decorations[0]._).toEqual({ loading: false })
  })

  test('delete decoration', async () => {
    const decoration = {
      id: 1,
      type: 'left_border_color',
      value_provider_type: 'single_select_color',
      _: {
        loading: false,
      },
    }
    const view = {
      id: 42,
      decorations: [decoration],
    }

    mockServer.deleteDecoration(decoration)

    await store.dispatch('view/deleteDecoration', {
      view,
      decoration,
    })

    expect(view.decorations.length).toBe(0)
  })
})
