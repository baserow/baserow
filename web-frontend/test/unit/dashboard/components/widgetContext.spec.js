import { mount } from '@vue/test-utils'

import WidgetContext from '@baserow/modules/dashboard/components/widget/WidgetContext'

function mountWidgetContext(hasPermission) {
  return mount(WidgetContext, {
    props: {
      dashboard: { workspace: { id: 1 } },
      widget: { id: 1 },
    },
    global: {
      mocks: {
        $hasPermission: hasPermission,
        $t: (key) => key,
      },
      stubs: {
        Context: {
          template: '<div><slot /></div>',
        },
      },
    },
  })
}

describe('WidgetContext', () => {
  test('shows deletion when the widget can be deleted without layout permission', () => {
    const requestedPermissions = []
    const wrapper = mountWidgetContext((permission) => {
      requestedPermissions.push(permission)
      return permission === 'dashboard.widget.delete'
    })

    expect(wrapper.find('.context__menu-item-link--delete').exists()).toBe(true)
    expect(requestedPermissions).toEqual(['dashboard.widget.delete'])
  })
})
