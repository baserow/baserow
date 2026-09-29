import { mount } from '@vue/test-utils'

import DashboardContentHeader from '@baserow/modules/dashboard/components/DashboardContentHeader'

function mountDashboardContentHeader({ isEditMode }) {
  return mount(DashboardContentHeader, {
    props: {
      dashboard: {
        id: 1,
        name: 'Dashboard',
        description: '',
        workspace: { id: 1 },
      },
    },
    global: {
      mocks: {
        $store: {
          getters: {
            'dashboardApplication/isEditMode': isEditMode,
          },
        },
        $t: (key) => key,
      },
      stubs: {
        Editable: {
          props: ['value'],
          template: '<span>{{ value }}</span>',
        },
      },
    },
  })
}

describe('DashboardContentHeader', () => {
  test('shows the dashboard title', () => {
    const wrapper = mountDashboardContentHeader({
      isEditMode: true,
    })

    expect(wrapper.text()).toContain('Dashboard')
  })

  test('only shows title and description edit actions in edit mode', () => {
    const viewModeWrapper = mountDashboardContentHeader({ isEditMode: false })
    const editModeWrapper = mountDashboardContentHeader({ isEditMode: true })

    expect(viewModeWrapper.find('.dashboard-app__edit').exists()).toBe(false)
    expect(editModeWrapper.findAll('.dashboard-app__edit')).toHaveLength(2)
  })
})
