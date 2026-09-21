import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, test } from 'vitest'

import EditRoleContext from '@baserow/modules/core/components/settings/members/EditRoleContext'

const workspace = { id: 12 }
const subject = { id: 34, role_uid: 'MEMBER' }
const roles = [
  {
    uid: 'MEMBER',
    name: 'Member',
    isVisible: true,
    isDeactivated: false,
    isBillable: false,
    showIsBillable: true,
  },
  {
    uid: 'ADMIN',
    name: 'Admin',
    isVisible: true,
    isDeactivated: false,
    isBillable: true,
    showIsBillable: true,
  },
]

const registeredRoles = roles.map((role) => ({
  getUid: () => role.uid,
  getDeactivatedClickModal: () => null,
}))

const mountContext = (showCommercialInfo) =>
  mountSuspended(EditRoleContext, {
    props: {
      workspace,
      subject,
      roles,
      roleValueColumn: 'role_uid',
      showCommercialInfo,
    },
    global: {
      mocks: {
        $registry: { getAll: () => registeredRoles },
        $t: (key) => key,
      },
      stubs: {
        Context: { template: '<div><slot /></div>' },
        Badge: { template: '<span class="badge"><slot /></span>' },
      },
    },
  })

describe('EditRoleContext', () => {
  test('shows commercial role information by default', async () => {
    const wrapper = await mountContext(undefined)

    expect(wrapper.html()).toMatchSnapshot()
  })

  test('can hide all commercial role information', async () => {
    const wrapper = await mountContext(false)

    expect(wrapper.html()).toMatchSnapshot()
  })
})
