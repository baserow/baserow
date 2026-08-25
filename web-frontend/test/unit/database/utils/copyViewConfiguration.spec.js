import { TestApp } from '@baserow/test/helpers/testApp'
import { expect } from 'vitest'

import {
  getCompatibleSourceViews,
  getDestinationCopyOptions,
  getEnabledCopyOptionKeys,
  copyViewConfiguration,
} from '@baserow/modules/database/utils/copyViewConfiguration'

describe('getEnabledCopyOptionKeys', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => testApp.afterEach())

  const view = (type) => ({ id: 1, type })

  // The TestApp registers the premium view decorators, but the test workspace
  // has no premium license, so they are deactivated and the `decorations`
  // option is disabled to prevent a copy that the backend would reject.
  test('grid to grid enables every option with an available decorator', () => {
    const registry = testApp.getRegistry()
    expect(
      getEnabledCopyOptionKeys(registry, view('grid'), view('grid'))
    ).toEqual([
      'field_visibility',
      'field_order',
      'field_widths',
      'view_settings',
      'filters',
      'sorts',
      'group_bys',
      'default_row_values',
    ])

    const decorator = Object.values(registry.getAll('viewDecorator'))[0]
    const isDeactivatedSpy = vi
      .spyOn(Object.getPrototypeOf(decorator), 'isDeactivated')
      .mockReturnValue(false)
    expect(
      getEnabledCopyOptionKeys(registry, view('grid'), view('grid'))
    ).toContain('decorations')
    isDeactivatedSpy.mockRestore()
  })

  test('grid to gallery disables grid specific options', () => {
    const registry = testApp.getRegistry()
    expect(
      getEnabledCopyOptionKeys(registry, view('grid'), view('gallery'))
    ).toEqual([
      'field_visibility',
      'field_order',
      'filters',
      'sorts',
      'default_row_values',
    ])
    // The intersection is symmetric on the option keys.
    expect(
      getEnabledCopyOptionKeys(registry, view('gallery'), view('grid'))
    ).toEqual(getEnabledCopyOptionKeys(registry, view('grid'), view('gallery')))
  })

  test('form views support no options at all', () => {
    const registry = testApp.getRegistry()
    expect(
      getEnabledCopyOptionKeys(registry, view('form'), view('grid'))
    ).toEqual([])
    expect(
      getEnabledCopyOptionKeys(registry, view('grid'), view('form'))
    ).toEqual([])
  })

  test('compatible source views exclude the destination and dead ends', () => {
    const registry = testApp.getRegistry()
    const grid = { id: 1, type: 'grid' }
    const otherGrid = { id: 2, type: 'grid' }
    const form = { id: 3, type: 'form' }

    expect(
      getCompatibleSourceViews(registry, [grid, otherGrid, form], grid)
    ).toEqual([otherGrid])
    // A form view can neither receive nor provide configuration, and a table
    // with a single view has no compatible sources at all.
    expect(getCompatibleSourceViews(registry, [grid, form], form)).toEqual([])
    expect(getCompatibleSourceViews(registry, [grid], grid)).toEqual([])
  })

  test('destination options are sorted by order', () => {
    const registry = testApp.getRegistry()
    const options = getDestinationCopyOptions(registry, view('grid'))
    const orders = options.map((option) => option.getOrder())
    expect(orders).toEqual([...orders].sort((a, b) => a - b))
    expect(options.map((option) => option.getType())).toContain('field_widths')
    expect(
      getDestinationCopyOptions(registry, view('gallery')).map((option) =>
        option.getType()
      )
    ).not.toContain('field_widths')
  })
})

describe('copyViewConfiguration', () => {
  let testApp = null
  let mockServer = null

  const sourceViewId = 1
  const destViewId = 2

  beforeEach(() => {
    testApp = new TestApp()
    mockServer = testApp.mockServer

    testApp.store.dispatch('view/forceCreate', {
      data: {
        id: sourceViewId,
        type: 'grid',
        table_id: 10,
        filter_type: 'OR',
        filters_disabled: true,
        row_height_size: 'large',
      },
    })
    testApp.store.dispatch('view/forceCreate', {
      data: {
        id: destViewId,
        type: 'grid',
        table_id: 10,
        filter_type: 'AND',
        filters_disabled: false,
        row_height_size: 'small',
      },
    })
  })

  afterEach(() => testApp.afterEach())

  const getContext = () => {
    const app = testApp.getApp()
    return {
      $store: testApp.store,
      $client: app.$client,
      $registry: app.$registry,
      $bus: app.$bus,
    }
  }

  const getView = (id) => testApp.store.getters['view/get'](id)

  const mockCopyResponse = (responseView, requests = []) => {
    mockServer.mock
      .onPost(`/database/views/${destViewId}/copy-configuration/`)
      .reply((config) => {
        requests.push(JSON.parse(config.data))
        return [200, responseView]
      })
    return requests
  }

  test('makes a single request and applies the response atomically', async () => {
    const sourceView = getView(sourceViewId)
    const destView = getView(destViewId)

    // Existing destination configuration that the response replaces.
    await testApp.store.dispatch('view/forceCreateFilter', {
      view: destView,
      values: { id: 70, field: 100, type: 'equal', value: 'old', group: null },
    })

    const requests = mockCopyResponse({
      id: destViewId,
      table_id: 10,
      filter_type: 'OR',
      filters_disabled: true,
      filters: [
        {
          id: 90,
          view: destViewId,
          field: 100,
          type: 'equal',
          value: 'a',
          group: 80,
        },
      ],
      filter_groups: [
        { id: 80, view: destViewId, filter_type: 'OR', parent_group: null },
      ],
      sortings: [
        {
          id: 91,
          view: destViewId,
          field: 100,
          order: 'DESC',
          type: 'default',
        },
      ],
      group_bys: [],
      decorations: [],
    })

    await copyViewConfiguration(getContext(), {
      sourceView,
      destView,
      categories: ['filters', 'sorts'],
    })

    expect(requests).toEqual([
      { source_view_id: sourceViewId, categories: ['filters', 'sorts'] },
    ])

    // The whole payload has been applied to the store in one go.
    expect(destView.filter_type).toBe('OR')
    expect(destView.filters_disabled).toBe(true)
    expect(destView.filters.map((f) => f.id)).toEqual([90])
    expect(destView.filter_groups.map((g) => g.id)).toEqual([80])
    expect(destView.sortings.map((s) => s.id)).toEqual([91])

    // The source view is untouched.
    const sourceView2 = getView(sourceViewId)
    expect(sourceView2.filters).toEqual([])
  })

  test('categories not supported by the views are not requested', async () => {
    testApp.store.dispatch('view/forceCreate', {
      data: {
        id: 3,
        type: 'gallery',
        table_id: 10,
        filter_type: 'AND',
        filters_disabled: false,
      },
    })
    const sourceView = getView(sourceViewId)
    const destView = getView(3)

    const requests = []
    mockServer.mock
      .onPost(`/database/views/3/copy-configuration/`)
      .reply((config) => {
        requests.push(JSON.parse(config.data))
        return [
          200,
          {
            id: 3,
            table_id: 10,
            filters: [],
            filter_groups: [],
            sortings: [],
            group_bys: [],
            decorations: [],
          },
        ]
      })

    await copyViewConfiguration(getContext(), {
      sourceView,
      destView,
      categories: ['filters', 'field_widths', 'view_settings', 'group_bys'],
    })

    // The grid specific categories are stripped from the request.
    expect(requests).toEqual([
      { source_view_id: sourceViewId, categories: ['filters'] },
    ])
  })

  test('table-refresh is only emitted when the destination view is selected', async () => {
    const sourceView = getView(sourceViewId)
    const destView = getView(destViewId)
    const app = testApp.getApp()
    const emitSpy = vi.spyOn(app.$bus, '$emit')

    mockCopyResponse({
      id: destViewId,
      table_id: 10,
      filters: [],
      filter_groups: [],
      sortings: [],
      group_bys: [],
      decorations: [],
    })

    await copyViewConfiguration(getContext(), {
      sourceView,
      destView,
      categories: ['filters'],
    })
    expect(emitSpy).not.toHaveBeenCalledWith('table-refresh', expect.anything())

    testApp.store.commit('view/SET_SELECTED', destView)
    await copyViewConfiguration(getContext(), {
      sourceView,
      destView,
      categories: ['filters'],
    })
    expect(emitSpy).toHaveBeenCalledWith('table-refresh', {
      tableId: 10,
      includeFieldOptions: false,
    })
  })

  test('field option categories refresh the field options', async () => {
    const sourceView = getView(sourceViewId)
    const destView = getView(destViewId)
    const app = testApp.getApp()
    const emitSpy = vi.spyOn(app.$bus, '$emit')
    testApp.store.commit('view/SET_SELECTED', destView)

    mockCopyResponse({
      id: destViewId,
      table_id: 10,
      filters: [],
      filter_groups: [],
      sortings: [],
      group_bys: [],
      decorations: [],
    })

    await copyViewConfiguration(getContext(), {
      sourceView,
      destView,
      categories: ['field_visibility', 'field_widths'],
    })
    expect(emitSpy).toHaveBeenCalledWith('table-refresh', {
      tableId: 10,
      includeFieldOptions: true,
    })

    // Options that neither refresh rows nor field options don't emit at all.
    emitSpy.mockClear()
    await copyViewConfiguration(getContext(), {
      sourceView,
      destView,
      categories: ['view_settings'],
    })
    expect(emitSpy).not.toHaveBeenCalledWith('table-refresh', expect.anything())
  })

  test('a failing request leaves the store untouched', async () => {
    const sourceView = getView(sourceViewId)
    const destView = getView(destViewId)

    mockServer.mock
      .onPost(`/database/views/${destViewId}/copy-configuration/`)
      .reply(400, {
        error: 'ERROR_VIEW_CONFIGURATION_COPY_CATEGORY_NOT_SUPPORTED',
        detail: '',
      })

    await expect(
      copyViewConfiguration(getContext(), {
        sourceView,
        destView,
        categories: ['filters'],
      })
    ).rejects.toThrow()

    expect(destView.filter_type).toBe('AND')
    expect(destView.filters).toEqual([])
  })
})
