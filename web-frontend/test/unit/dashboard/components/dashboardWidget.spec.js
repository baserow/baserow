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

/** Mount a widget with reactive dispatch state and the real skeleton directive. */
function mountDashboardWidget({
  isMisconfigured = false,
  isLoading = true,
  showHeaderBorder = true,
} = {}) {
  const data = reactive(isLoading ? {} : { 1: { result: 42, _loaded: true } })
  const widgetType = {
    name: 'Chart',
    component: LoadingWidgetContent,
    isLoading: (_widget, data) => !data[1] || data[1]._loading === true,
    hasLoadedData: (_widget, data) => data[1]?._loaded === true,
    isMisconfigured: () => isMisconfigured,
    hasCard: true,
    isDisplayWidget: true,
    getDataSourceData: (_widget, data) => data[1],
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
  test('shows the filtered indicator only for filtered results', async () => {
    const { wrapper, data } = mountDashboardWidget({ isLoading: false })
    expect(wrapper.find('.dashboard-widget__filter-status').exists()).toBe(
      false
    )
    data[1] = { result: 10, _is_filtered: true }
    await nextTick()
    const indicator = wrapper.get('.dashboard-widget__filter-status')
    expect(indicator.attributes('aria-label')).toBe('widget.filteredResults')
    expect(indicator.find('.iconoir-filter').exists()).toBe(true)
    expect(indicator.element.previousElementSibling.textContent).toBe(
      'Loading chart'
    )
    data[1] = { result: 42 }
    await nextTick()
    expect(wrapper.find('.dashboard-widget__filter-status').exists()).toBe(
      false
    )
  })

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

  test('retains loaded content during refresh', async () => {
    const { wrapper, data } = mountDashboardWidget({ isLoading: false })
    const content = wrapper.get('.loading-widget-content').element
    data[1] = { ...data[1], _loading: true }
    await nextTick()

    expect(wrapper.classes()).not.toContain('skeleton-loading')
    expect(wrapper.get('.loading-widget-content').element).toBe(content)
    expect(wrapper.get('.loading-widget-content').text()).toBe('false')
    expect(wrapper.get('[role="status"]').attributes('aria-label')).toBe(
      'dashboard.widgetsLoading'
    )
    expect(wrapper.html()).toMatchSnapshot('refreshing')

    data[1] = { result: null, _loaded: true }
    await nextTick()
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
    data[1]._loading = true
    await nextTick()
    expect(wrapper.classes()).not.toContain('skeleton-loading')
  })

  test('delegates header presentation to the registered widget type', () => {
    const { wrapper } = mountDashboardWidget({ showHeaderBorder: false })

    expect(wrapper.get('.widget__header').classes()).toContain(
      'widget__header--no-border'
    )
  })
})
