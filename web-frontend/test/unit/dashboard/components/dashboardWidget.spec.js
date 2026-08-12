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

function mountDashboardWidget() {
  const widgetType = {
    name: 'Chart',
    component: LoadingWidgetContent,
    isLoading: () => true,
  }

  return mount(DashboardWidget, {
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
            'dashboardApplication/getDataForDataSource': () => undefined,
            'dashboardApplication/getDataSourceById': () => undefined,
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
}

describe('DashboardWidget', () => {
  test('keeps the header and context menu available while a chart is loading', () => {
    const wrapper = mountDashboardWidget()

    expect(wrapper.find('.widget__header-title').text()).toBe('Loading chart')
    expect(wrapper.find('widget-context-menu-stub').exists()).toBe(true)
    expect(wrapper.find('.loading-widget-content').text()).toBe('true')
  })
})
