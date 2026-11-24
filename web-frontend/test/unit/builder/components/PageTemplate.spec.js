import MockAdapter from 'axios-mock-adapter'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import flushPromises from 'flush-promises'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import PageTemplate from '@baserow/modules/builder/components/page/PageTemplate'

const elementValues = {
  page_id: 2,
  parent_element_id: null,
  place_in_container: null,
  visibility: 'all',
  roles: [],
  role_type: 'allow_all',
  styles: {},
  css_classes: '',
  style_background_file: null,
}

const dataSourceValues = {
  type: 'local_baserow_list_rows',
  table_id: 3,
  filters: [],
  sortings: [],
  schema: null,
}

const permissionDenied = {
  error: 'PERMISSION_DENIED',
  detail: "You don't have the required permission to execute this operation.",
}

describe('PageTemplate', () => {
  let store
  let registry
  let mock
  let runRequests
  let originalResizeObserver

  beforeEach(() => {
    const app = useNuxtApp()
    store = app.$store
    registry = app.$registry
    mock = new MockAdapter(app.$client, { onNoMatch: 'throwException' })
    runRequests = []
    vi.useFakeTimers()
    originalResizeObserver = globalThis.ResizeObserver
    globalThis.ResizeObserver = class {
      disconnect = vi.fn()
      observe = vi.fn()
    }
  })

  afterEach(() => {
    mock.restore()
    vi.useRealTimers()
    globalThis.ResizeObserver = originalResizeObserver
  })

  const mockBuilderServer = () => {
    mock.onGet('/application/1/user-sources/').reply(200, [])
    mock.onGet('application/1/integrations/').reply(200, [])
    mock.onGet('builder/page/1/data-sources/').reply(200, [
      {
        id: 7,
        page_id: 1,
        name: 'Projects',
        order: '1',
        ...dataSourceValues,
      },
    ])
    mock.onGet('builder/page/1/elements/').reply(200, [])
    mock.onGet('builder/page/1/workflow_actions/').reply(200, [])
    mock
      .onGet('builder/page/2/data-sources/')
      .reply(200, [
        { id: 8, page_id: 2, name: 'Tasks', order: '1', ...dataSourceValues },
      ])
    mock.onGet('builder/page/2/elements/').reply(200, [
      {
        ...elementValues,
        id: 20,
        order: '1',
        type: 'heading',
        level: 1,
        value: { formula: "'Projects overview'" },
      },
      {
        ...elementValues,
        id: 21,
        order: '2',
        type: 'table',
        data_source_id: 7,
        schema_property: null,
        items_per_page: 10,
        button_load_more_label: { formula: '' },
        orientation: { desktop: 'horizontal' },
        fields: [
          {
            id: 1,
            type: 'text',
            name: 'Name',
            value: { formula: "get('current_record.field_1')" },
            styles: {},
          },
        ],
        property_options: [],
      },
      {
        ...elementValues,
        id: 22,
        order: '3',
        type: 'record_selector',
        data_source_id: 7,
        items_per_page: 20,
        label: { formula: '' },
        placeholder: { formula: '' },
        default_value: { formula: "'1'" },
        option_name_suffix: { formula: '' },
        multiple: false,
        required: false,
        property_options: [],
      },
    ])
    mock.onGet('builder/page/2/workflow_actions/').reply(200, [])
    mock.onPost(/dispatch-data-sources\/$/).reply((config) => {
      runRequests.push(config.url)
      return [401, permissionDenied]
    })
    mock.onPost(/\/dispatch\/$/).reply((config) => {
      runRequests.push(config.url)
      return [401, permissionDenied]
    })
    mock.onGet(/record-names\/$/).reply((config) => {
      runRequests.push(config.url)
      return [401, permissionDenied]
    })
  }

  const createBuilder = () => {
    const builder = registry.get('application', 'builder').populate({
      id: 1,
      name: 'Project tracker',
      order: 1,
      type: 'builder',
      workspace: { id: 1, name: 'Templates' },
      favicon_file: null,
      theme: {},
      pages: [
        {
          id: 1,
          builder_id: 1,
          name: '__shared__',
          path: '__shared__',
          shared: true,
          order: 1,
          path_params: [],
          query_params: [],
        },
        {
          id: 2,
          builder_id: 1,
          name: 'Projects',
          path: '/projects/:id',
          shared: false,
          order: 2,
          path_params: [{ name: 'id', type: 'numeric' }],
          query_params: [],
        },
      ],
    })
    store.dispatch('application/forceCreate', builder)
    return store.getters['application/get'](1)
  }

  test('shows the page without live data, without a spinner, a run or a toast', async () => {
    mockBuilderServer()
    const builder = createBuilder()

    const wrapper = await mountSuspended(PageTemplate, {
      props: { pageValue: { builder, page: builder.pages[1] } },
      global: {
        provide: { withoutLiveData: true },
        stubs: { PageHeader: true, PageSidePanels: true },
      },
    })
    await vi.advanceTimersByTimeAsync(1000)
    await wrapper.find('.preview-navigation-bar-input').setValue('3')
    await vi.advanceTimersByTimeAsync(1000)
    await wrapper
      .find('.choice-element .ab-dropdown__selected')
      .trigger('click')
    await vi.advanceTimersByTimeAsync(1000)
    await flushPromises()

    expect(wrapper.text()).toContain('Projects overview')
    expect(wrapper.find('.table-element').exists()).toBe(true)
    expect(wrapper.find('.loading-spinner').exists()).toBe(false)
    expect(
      wrapper.find('.preview-navigation-bar__user-selector').exists()
    ).toBe(false)
    expect(runRequests).toEqual([])
    expect(store.state.toast.items).toEqual([])
    wrapper.unmount()
  })
})
