import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, test } from 'vitest'

import WorkspaceRoleSelector from '@baserow/modules/core/components/workspace/WorkspaceRoleSelector'

const workspace = { id: 12 }
const roles = [
  {
    uid: 'MEMBER',
    name: 'Member',
    isDeactivated: false,
    isBillable: false,
    showIsBillable: true,
  },
  {
    uid: 'ADMIN',
    name: 'Admin',
    isDeactivated: false,
    isBillable: true,
    showIsBillable: true,
  },
]

const mountSelector = (showCommercialInfo) =>
  mountSuspended(WorkspaceRoleSelector, {
    props: {
      modelValue: 'MEMBER',
      workspace,
      roles,
      showCommercialInfo,
    },
    global: {
      mocks: {
        $registry: { getAll: () => ({}) },
        $t: (key) => key,
      },
      stubs: {
        Dropdown: { template: '<div><slot /></div>' },
        DropdownItem: { template: '<div class="dropdown-item"><slot /></div>' },
        Badge: { template: '<span class="badge"><slot /></span>' },
      },
    },
  })

describe('WorkspaceRoleSelector', () => {
  test('shows commercial role information by default', async () => {
    const wrapper = await mountSelector(undefined)

    expect(wrapper.html()).toMatchSnapshot()
  })

  test('can hide all commercial role information', async () => {
    const wrapper = await mountSelector(false)

    expect(wrapper.html()).toMatchSnapshot()
  })
})

test('uses role metadata for the selected icon and can hide it', async () => {
  const wrapper = await mountSuspended(WorkspaceRoleSelector, {
    props: {
      workspace,
      modelValue: 'CUSTOM',
      roles: [{ uid: 'CUSTOM', name: 'Custom role', icon: 'iconoir-star' }],
      showRoleIcons: true,
    },
    global: { mocks: { $registry: { getAll: () => ({}) } } },
  })
  expect(wrapper.get('.dropdown__selected-icon').classes()).toContain(
    'iconoir-star'
  )
  await wrapper.setProps({ showRoleIcons: false })
  expect(wrapper.find('.dropdown__selected-icon').exists()).toBe(false)
  wrapper.unmount()
})
