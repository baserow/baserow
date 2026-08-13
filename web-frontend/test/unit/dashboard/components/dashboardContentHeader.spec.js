import { mount } from '@vue/test-utils'

import DashboardContentHeader from '@baserow/modules/dashboard/components/DashboardContentHeader'

const CreateWidgetButtonStub = {
  name: 'CreateWidgetButton',
  props: ['dashboard'],
  emits: ['widget-variation-selected'],
  template: `
    <button
      data-testid="dashboard-add-widget-button"
      @click="$emit('widget-variation-selected', { type: 'summary' })"
    >
      Add widget
    </button>
  `,
}

function mountDashboardContentHeader({
  isEditMode,
  canCreateWidget,
  isEmpty = false,
}) {
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
        $hasPermission: () => canCreateWidget,
        $store: {
          getters: {
            'dashboardApplication/isEditMode': isEditMode,
            'dashboardApplication/isEmpty': isEmpty,
          },
        },
        $t: (key) => key,
      },
      stubs: {
        CreateWidgetButton: CreateWidgetButtonStub,
        Editable: {
          props: ['value'],
          template: '<span>{{ value }}</span>',
        },
      },
    },
  })
}

describe('DashboardContentHeader', () => {
  test('shows the add widget action in edit mode and forwards its selection', async () => {
    const wrapper = mountDashboardContentHeader({
      isEditMode: true,
      canCreateWidget: true,
    })

    const addWidgetButton = wrapper.get(
      '[data-testid="dashboard-add-widget-button"]'
    )
    await addWidgetButton.trigger('click')

    expect(wrapper.emitted('widget-variation-selected')).toEqual([
      [{ type: 'summary' }],
    ])
  })

  test('hides the add widget action outside edit mode, without permission, or when empty', () => {
    const viewModeWrapper = mountDashboardContentHeader({
      isEditMode: false,
      canCreateWidget: true,
    })
    const noPermissionWrapper = mountDashboardContentHeader({
      isEditMode: true,
      canCreateWidget: false,
    })
    const emptyDashboardWrapper = mountDashboardContentHeader({
      isEditMode: true,
      canCreateWidget: true,
      isEmpty: true,
    })

    expect(
      viewModeWrapper
        .find('[data-testid="dashboard-add-widget-button"]')
        .exists()
    ).toBe(false)
    expect(
      noPermissionWrapper
        .find('[data-testid="dashboard-add-widget-button"]')
        .exists()
    ).toBe(false)
    expect(
      emptyDashboardWrapper
        .find('[data-testid="dashboard-add-widget-button"]')
        .exists()
    ).toBe(false)
  })
})
