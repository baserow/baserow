import { mount } from '@vue/test-utils'
import { vi } from 'vitest'

import DashboardHeader from '@baserow/modules/dashboard/components/DashboardHeader'

const CreateWidgetButtonStub = {
  name: 'CreateWidgetButton',
  props: ['loading'],
  emits: ['widget-variation-selected'],
  template: `
    <button
      data-testid="dashboard-add-widget-button"
      :data-loading="loading"
      @click="$emit('widget-variation-selected', { type: 'summary' })"
    >
      Add widget
    </button>
  `,
}

function mountDashboardHeader({
  isEditMode,
  canCreateWidget,
  isCreatingWidget = false,
}) {
  const dispatch = vi.fn()
  const wrapper = mount(DashboardHeader, {
    props: {
      dashboard: {
        id: 1,
        workspace: { id: 1 },
      },
      isCreatingWidget,
    },
    global: {
      mocks: {
        $hasPermission: () => canCreateWidget,
        $store: {
          getters: {
            'dashboardApplication/isEditMode': isEditMode,
            'dashboardApplication/isLoading': false,
          },
          dispatch,
        },
        $t: (key) => key,
      },
      stubs: {
        Button: {
          emits: ['click'],
          template:
            '<button data-testid="done-editing" @click="$emit(\'click\')"><slot /></button>',
        },
        CreateWidgetButton: CreateWidgetButtonStub,
        DashboardHeaderMenuItems: {
          template: '<div data-testid="dashboard-header-menu-items"></div>',
        },
      },
    },
  })

  return { wrapper, dispatch }
}

describe('DashboardHeader', () => {
  test('shows the add widget action beside Done editing and forwards selection', async () => {
    const { wrapper } = mountDashboardHeader({
      isEditMode: true,
      canCreateWidget: true,
      isCreatingWidget: true,
    })

    const addWidgetButton = wrapper.get(
      '[data-testid="dashboard-add-widget-button"]'
    )

    expect(addWidgetButton.attributes('data-loading')).toBe('true')
    expect(wrapper.get('[data-testid="done-editing"]').exists()).toBe(true)

    await addWidgetButton.trigger('click')

    expect(wrapper.emitted('widget-variation-selected')).toEqual([
      [{ type: 'summary' }],
    ])
  })

  test('only shows the add widget action in edit mode for users with permission', () => {
    const viewMode = mountDashboardHeader({
      isEditMode: false,
      canCreateWidget: true,
    })
    const withoutPermission = mountDashboardHeader({
      isEditMode: true,
      canCreateWidget: false,
    })

    expect(
      viewMode.wrapper
        .find('[data-testid="dashboard-add-widget-button"]')
        .exists()
    ).toBe(false)
    expect(
      withoutPermission.wrapper
        .find('[data-testid="dashboard-add-widget-button"]')
        .exists()
    ).toBe(false)
  })

  test('leaves edit mode when Done editing is clicked', async () => {
    const { wrapper, dispatch } = mountDashboardHeader({
      isEditMode: true,
      canCreateWidget: true,
    })

    await wrapper.get('[data-testid="done-editing"]').trigger('click')

    expect(dispatch).toHaveBeenCalledWith('dashboardApplication/toggleEditMode')
  })
})
