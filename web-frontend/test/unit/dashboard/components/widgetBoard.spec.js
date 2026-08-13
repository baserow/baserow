import { mount } from '@vue/test-utils'

import WidgetBoard from '@baserow/modules/dashboard/components/WidgetBoard'

describe('WidgetBoard', () => {
  test('renders a loader instead of widgets in its ClientOnly fallback', () => {
    const wrapper = mount(WidgetBoard, {
      props: {
        dashboard: { workspace: { id: 1 } },
      },
      global: {
        mocks: {
          $store: {
            getters: {
              'dashboardApplication/getWidgets': [{ id: 1, title: 'Summary' }],
            },
          },
        },
        stubs: {
          ClientOnly: {
            template: '<div><slot name="fallback" /></div>',
          },
          DashboardWidgetGridLoading: {
            template: '<div data-testid="dashboard-widget-grid-loading"></div>',
          },
          DashboardWidget: {
            props: ['widget'],
            template:
              '<article class="dashboard-widget-stub">{{ widget.title }}</article>',
          },
        },
      },
    })

    expect(
      wrapper.find('[data-testid="dashboard-widget-board-fallback"]').exists()
    ).toBe(true)
    expect(
      wrapper.find('[data-testid="dashboard-widget-grid-loading"]').exists()
    ).toBe(true)
    expect(wrapper.find('.dashboard-widget-stub').exists()).toBe(false)
  })
})
