import { mount } from '@vue/test-utils'
import { ref } from 'vue'

import WidgetContext from '@baserow/modules/dashboard/components/widget/WidgetContext'

function mountWidgetContext(
  hasPermission,
  {
    isDisplayWidget = false,
    tableId = null,
    createDashboardWidget = vi.fn(),
    widgetCreation = ref(null),
  } = {}
) {
  return mount(WidgetContext, {
    props: {
      dashboard: { id: 7, workspace: { id: 1 } },
      widget: { id: 1, type: 'summary', data_source_id: 3 },
    },
    global: {
      provide: {
        createDashboardWidget,
        dashboardWidgetCreation: widgetCreation,
      },
      mocks: {
        $hasPermission: hasPermission,
        $registry: {
          get: () => ({
            isDisplayWidget,
            getDataSourceId: (widget) => widget.data_source_id,
          }),
        },
        $store: {
          getters: {
            'dashboardApplication/getDataSourceById': () =>
              tableId ? { id: 3, table_id: tableId } : null,
          },
        },
        $t: (key) => key,
      },
      stubs: {
        Context: {
          template: '<div><slot /></div>',
          methods: { hide() {}, show() {} },
        },
      },
    },
  })
}

describe('WidgetContext', () => {
  test('shows deletion when the widget can be deleted without layout permission', () => {
    const requestedPermissions = []
    const wrapper = mountWidgetContext((permission) => {
      requestedPermissions.push(permission)
      return permission === 'dashboard.widget.delete'
    })

    expect(wrapper.find('.context__menu-item-link--delete').exists()).toBe(true)
    expect(requestedPermissions).toEqual(['dashboard.widget.delete'])
  })

  test.each([
    [{ isDisplayWidget: true, tableId: 5 }, true],
    [{ isDisplayWidget: true, tableId: null }, false],
    [{ isDisplayWidget: false, tableId: 5 }, false],
  ])('offers a filter for a widget showing a table %o', (options, shown) => {
    const wrapper = mountWidgetContext(() => true, options)

    expect(wrapper.text().includes('widgetContext.addFilter')).toBe(shown)
  })

  test('creates a filter applied to the widget', async () => {
    const createDashboardWidget = vi.fn().mockResolvedValue({ id: 9 })
    const wrapper = mountWidgetContext(() => true, {
      isDisplayWidget: true,
      tableId: 5,
      createDashboardWidget,
    })

    await wrapper.find('.context__menu-item-link').trigger('click')

    expect(createDashboardWidget).toHaveBeenCalledWith({
      type: 'text_filter',
      params: {
        target_filters: [
          expect.objectContaining({
            target_widget_id: 1,
            group: { filter_type: 'AND', filters: [], filter_groups: [] },
          }),
        ],
      },
    })
  })

  test('disables adding a filter during another widget creation', async () => {
    const createDashboardWidget = vi.fn()
    const wrapper = mountWidgetContext(() => true, {
      isDisplayWidget: true,
      tableId: 5,
      createDashboardWidget,
      widgetCreation: ref({ loading: true }),
    })

    const addFilter = wrapper.get('[role="button"]')
    expect(addFilter.attributes('aria-disabled')).toBe('true')
    await addFilter.trigger('click')
    expect(createDashboardWidget).not.toHaveBeenCalled()
  })
})
