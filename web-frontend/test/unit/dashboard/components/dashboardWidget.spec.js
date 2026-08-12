import { mount } from '@vue/test-utils'

import DashboardWidget from '@baserow/modules/dashboard/components/widget/DashboardWidget'

const LoadingWidgetContent = {
  name: 'LoadingWidgetContent',
  props: {
    loading: {
      type: Boolean,
      required: true,
    },
  },
  template: '<div class="loading-widget-content">{{ loading }}</div>',
}

function mountDashboardWidget({ dataSource, dataForDataSource } = {}) {
  const widgetType = {
    name: 'Chart',
    component: LoadingWidgetContent,
    isLoading: () => true,
  }

  const wrapper = mount(DashboardWidget, {
    props: {
      dashboard: { workspace: { id: 1 } },
      widget: {
        id: 1,
        type: 'chart',
        title: 'Loading chart',
        description: '',
        data_source_id: 1,
      },
      isLayoutEditable: true,
    },
    global: {
      mocks: {
        $hasPermission: () => true,
        $registry: {
          get: (namespace) => {
            if (namespace === 'dashboardWidget') {
              return widgetType
            }
            return null
          },
        },
        $store: {
          getters: {
            'dashboardApplication/getData': {},
            'dashboardApplication/getDataForDataSource': () =>
              dataForDataSource,
            'dashboardApplication/getDataSourceById': () => dataSource,
            'dashboardApplication/getSelectedWidgetId': null,
            'dashboardApplication/isEditMode': true,
          },
        },
        $t: (key) => key,
      },
      stubs: {
        Badge: true,
        WidgetContextMenu: true,
      },
    },
  })

  return { wrapper }
}

describe('DashboardWidget', () => {
  test('keeps the header and context menu available while a chart is loading', () => {
    const { wrapper } = mountDashboardWidget()

    expect(wrapper.find('.widget__header-title').text()).toBe('Loading chart')
    expect(wrapper.find('widget-context-menu-stub').exists()).toBe(true)
    expect(wrapper.find('.loading-widget-content').text()).toBe('true')
  })

  test('keeps invalid widget content visible with a configuration tooltip', () => {
    const { wrapper } = mountDashboardWidget({
      dataSource: { id: 1 },
      dataForDataSource: { _error: true },
    })

    const configurationStatus = wrapper.find(
      '.dashboard-widget__configuration-status'
    )
    expect(configurationStatus.exists()).toBe(true)
    expect(configurationStatus.attributes('aria-label')).toBe(
      'widget.fixConfiguration'
    )
    expect(wrapper.find('.loading-widget-content').text()).toBe('true')
  })
})
