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
  test('covers the header and data with one skeleton while the widget is loading', () => {
    const { wrapper } = mountDashboardWidget()

    expect(wrapper.classes()).toContain('skeleton-loading')
    for (const selector of [
      '.widget__header',
      'widget-context-menu-stub',
      '.loading-widget-content',
    ]) {
      expect(wrapper.get(selector).element.closest('.skeleton-loading')).toBe(
        wrapper.element
      )
    }
  })

  test('reveals the complete widget when its data arrives', async () => {
    const { wrapper, data } = mountDashboardWidget()

    expect(wrapper.attributes('aria-busy')).toBe('true')
    expect(wrapper.element.style.getPropertyValue('--skeleton-height')).toBe(
      '100%'
    )

    data[1] = { result: 42 }
    await nextTick()

    expect(wrapper.classes()).not.toContain('skeleton-loading')
    expect(wrapper.attributes('aria-busy')).toBeUndefined()
    expect(wrapper.get('.widget__header-title').text()).toBe('Loading chart')
    expect(wrapper.find('widget-context-menu-stub').exists()).toBe(true)
    expect(wrapper.get('.loading-widget-content').text()).toBe('false')
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
