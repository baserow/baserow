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

function mountDashboardWidget({
  isMisconfigured = false,
  showHeaderBorder = true,
} = {}) {
  const widgetType = {
    name: 'Chart',
    component: LoadingWidgetContent,
    isLoading: () => true,
    isMisconfigured: () => isMisconfigured,
    showHeaderBorder,
  }

  const wrapper = mount(DashboardWidget, {
    props: {
      dashboard: { workspace: { id: 1 } },
      widget: {
        id: 1,
        type: 'chart',
        title: 'Loading chart',
        description: '',
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
      isMisconfigured: true,
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

  test('delegates header presentation to the registered widget type', () => {
    const { wrapper } = mountDashboardWidget({ showHeaderBorder: false })

    expect(wrapper.get('.widget__header').classes()).toContain(
      'widget__header--no-border'
    )
  })
})
