import { mount } from '@vue/test-utils'
import { vi } from 'vitest'

import DashboardHeaderMenuItems from '@baserow/modules/dashboard/components/DashboardHeaderMenuItems'

function mountDashboardHeaderMenuItems({ canEdit }) {
  const dispatch = vi.fn()
  const wrapper = mount(DashboardHeaderMenuItems, {
    props: {
      dashboard: {
        id: 1,
        workspace: { id: 1 },
      },
    },
    global: {
      mocks: {
        $hasPermission: () => canEdit,
        $store: { dispatch },
        $t: (key) => key,
      },
      stubs: {
        ShareDashboardLink: {
          template: '<div data-testid="share-dashboard-link"></div>',
        },
      },
    },
  })

  return { wrapper, dispatch }
}

describe('DashboardHeaderMenuItems', () => {
  test('shows the edit mode and share dashboard items to users who can update the dashboard', async () => {
    const { wrapper, dispatch } = mountDashboardHeaderMenuItems({
      canEdit: true,
    })

    expect(wrapper.text()).toContain('dashboardHeaderMenuItems.editMode')
    expect(wrapper.find('[data-testid="share-dashboard-link"]').exists()).toBe(
      true
    )

    await wrapper.get('.header__filter-link').trigger('click')

    expect(dispatch).toHaveBeenCalledWith('dashboardApplication/toggleEditMode')
  })

  test('hides both items from users without the update permission', () => {
    const { wrapper } = mountDashboardHeaderMenuItems({ canEdit: false })

    expect(wrapper.text()).not.toContain('dashboardHeaderMenuItems.editMode')
    expect(wrapper.find('[data-testid="share-dashboard-link"]').exists()).toBe(
      false
    )
  })
})
