import { mount } from '@vue/test-utils'
import { describe, expect, test, vi } from 'vitest'

import WidgetBoard from '@baserow/modules/dashboard/components/WidgetBoard'
import DashboardWidget from '@baserow/modules/dashboard/components/widget/DashboardWidget'

const dashboard = {
  id: 10,
  workspace: { id: 20 },
}

const widgets = [
  { id: 1, order: 1, type: 'summary' },
  { id: 2, order: 2, type: 'summary' },
]

const mountWidgetBoard = ({ editMode = true, hasPermission = true } = {}) => {
  return mount(WidgetBoard, {
    props: { dashboard },
    global: {
      directives: {
        sortable: {},
      },
      mocks: {
        $store: {
          getters: {
            'dashboardApplication/isEditMode': editMode,
            'dashboardApplication/getWidgets': widgets,
          },
          dispatch: vi.fn(),
        },
        $hasPermission: vi.fn(() => hasPermission),
      },
      stubs: {
        DashboardWidget: {
          name: 'DashboardWidget',
          props: ['widget', 'dashboard', 'storePrefix', 'canOrderWidgets'],
          template: '<div class="dashboard-widget"></div>',
        },
      },
    },
  })
}

const mountDashboardWidget = ({
  editMode = true,
  canOrderWidgets = true,
  selectedWidgetId = widgets[0].id,
} = {}) => {
  return mount(DashboardWidget, {
    props: {
      dashboard,
      widget: widgets[0],
      canOrderWidgets,
    },
    global: {
      mocks: {
        $registry: {
          get: vi.fn(() => ({
            name: 'Summary',
            component: { template: '<div class="summary-widget"></div>' },
            isLoading: () => false,
          })),
        },
        $store: {
          getters: {
            'dashboardApplication/getSelectedWidgetId': selectedWidgetId,
            'dashboardApplication/isEditMode': editMode,
            'dashboardApplication/getData': {},
          },
          dispatch: vi.fn(),
        },
        $hasPermission: vi.fn(() => true),
      },
    },
  })
}

describe('WidgetBoard', () => {
  test('passes ordering permission to dashboard widgets in edit mode', () => {
    const wrapper = mountWidgetBoard()
    const renderedWidgets = wrapper.findAllComponents({
      name: 'DashboardWidget',
    })

    expect(renderedWidgets).toHaveLength(2)
    expect(renderedWidgets[0].props('canOrderWidgets')).toBe(true)
  })

  test('does not enable widget ordering outside edit mode', () => {
    const wrapper = mountWidgetBoard({ editMode: false })
    const renderedWidgets = wrapper.findAllComponents({
      name: 'DashboardWidget',
    })

    expect(renderedWidgets[0].props('canOrderWidgets')).toBe(false)
  })

  test('renders a dashboard widget drag handle only when selected and ordering is allowed', () => {
    const wrapper = mountDashboardWidget()

    expect(wrapper.find('[data-sortable-handle]').exists()).toBe(true)
    expect(wrapper.findAll('.dashboard-widget__drag-handle-dot')).toHaveLength(
      6
    )

    const withoutPermission = mountDashboardWidget({ canOrderWidgets: false })
    expect(withoutPermission.find('[data-sortable-handle]').exists()).toBe(
      false
    )

    const unselected = mountDashboardWidget({ selectedWidgetId: widgets[1].id })
    expect(unselected.find('[data-sortable-handle]').exists()).toBe(false)
  })
})
