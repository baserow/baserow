import { mount } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'

import DashboardWidget from '@baserow/modules/dashboard/components/widget/DashboardWidget'
import skeleton from '@baserow/modules/core/directives/skeleton'

let wrapper

afterEach(() => wrapper?.unmount())

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
  isLoading = true,
  showHeaderBorder = true,
} = {}) {
  const data = reactive(isLoading ? {} : { 1: { result: 42 } })
  const widgetType = {
    name: 'Chart',
    component: LoadingWidgetContent,
    isLoading: (_widget, data) => !data[1],
    isMisconfigured: () => isMisconfigured,
    showHeaderBorder,
  }

  wrapper = mount(DashboardWidget, {
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
      directives: { skeleton },
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
            'dashboardApplication/getData': data,
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

  return { wrapper, data }
}

describe('DashboardWidget', () => {
  test('keeps the header and context menu available while a chart is loading', () => {
    const { wrapper } = mountDashboardWidget()

    expect(wrapper.find('.widget__header-title').text()).toBe('Loading chart')
    expect(wrapper.find('widget-context-menu-stub').exists()).toBe(true)
    expect(wrapper.find('.loading-widget-content').text()).toBe('true')
    expect(wrapper.get('.loading-widget-content').classes()).toContain(
      'skeleton-loading'
    )
    expect(wrapper.get('.widget__header').classes()).not.toContain(
      'skeleton-loading'
    )
  })

  test('fills the widget content with a skeleton until its data arrives', async () => {
    const { wrapper, data } = mountDashboardWidget()
    const content = wrapper.get('.loading-widget-content')

    expect(content.attributes('aria-busy')).toBe('true')
    expect(content.element.style.getPropertyValue('--skeleton-height')).toBe(
      '100%'
    )

    data[1] = { result: 42 }
    await nextTick()

    expect(content.classes()).not.toContain('skeleton-loading')
    expect(content.attributes('aria-busy')).toBeUndefined()
    expect(content.text()).toBe('false')
  })

  test('keeps invalid widget content visible with a configuration tooltip', () => {
    const { wrapper } = mountDashboardWidget({
      isMisconfigured: true,
      isLoading: false,
    })

    const configurationStatus = wrapper.find(
      '.dashboard-widget__configuration-status'
    )
    expect(configurationStatus.exists()).toBe(true)
    expect(configurationStatus.attributes('aria-label')).toBe(
      'widget.fixConfiguration'
    )
    expect(wrapper.find('.loading-widget-content').text()).toBe('false')
    expect(wrapper.find('.skeleton-loading').exists()).toBe(false)
  })

  test('delegates header presentation to the registered widget type', () => {
    const { wrapper } = mountDashboardWidget({ showHeaderBorder: false })

    expect(wrapper.get('.widget__header').classes()).toContain(
      'widget__header--no-border'
    )
  })
})
