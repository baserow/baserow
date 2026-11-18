import { mount } from '@vue/test-utils'

import WidgetContext from '@baserow/modules/dashboard/components/widget/WidgetContext'

function mountWidgetContext(
  hasPermission,
  { isDisplayWidget = false, tableId = null, flag = true, dispatch } = {}
) {
  return mount(WidgetContext, {
    props: {
      dashboard: { id: 7, workspace: { id: 1 } },
      widget: { id: 1, type: 'summary', data_source_id: 3 },
    },
    global: {
      mocks: {
        $hasPermission: hasPermission,
        $featureFlagIsEnabled: () => flag,
        $registry: {
          get: (namespace, type) =>
            type === 'text_filter'
              ? { getType: () => 'text_filter', name: 'Filter' }
              : {
                  isDisplayWidget,
                  getDataSourceId: (widget) => widget.data_source_id,
                },
        },
        $store: {
          getters: {
            'dashboardApplication/getDataSourceById': () =>
              tableId ? { id: 3, table_id: tableId } : null,
          },
          dispatch: dispatch || vi.fn(),
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
    [{ isDisplayWidget: true, tableId: 5, flag: false }, false],
    [{ isDisplayWidget: false, tableId: 5 }, false],
  ])('offers a filter for a widget showing a table %o', (options, shown) => {
    const wrapper = mountWidgetContext(() => true, options)

    expect(wrapper.text().includes('widgetContext.addFilter')).toBe(shown)
  })

  test('creates a filter applied to the widget', async () => {
    const dispatch = vi.fn().mockResolvedValue({ id: 9 })
    const wrapper = mountWidgetContext(() => true, {
      isDisplayWidget: true,
      tableId: 5,
      dispatch,
    })

    await wrapper.find('.context__menu-item-link').trigger('click')

    expect(dispatch).toHaveBeenCalledWith('dashboardApplication/createWidget', {
      dashboard: { id: 7, workspace: { id: 1 } },
      widget: expect.objectContaining({
        type: 'text_filter',
        // The filter is set up for the table of the widget it was added from.
        filter_table_id: 5,
        target_filters: [
          expect.objectContaining({
            target_widget_id: 1,
            group: { filter_type: 'AND', filters: [], filter_groups: [] },
          }),
        ],
      }),
    })
  })
})
