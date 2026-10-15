import { mountSuspended } from '@nuxt/test-utils/runtime'
import { expect, test } from 'vitest'

import ScopeInheritedAccess from '@baserow_enterprise/components/invitation/ScopeInheritedAccess'

const roles = [
  { uid: 'ADMIN', name: 'Admin', isVisible: true },
  { uid: 'BUILDER', name: 'Builder', isVisible: true },
  { uid: 'VIEWER', name: 'Viewer', isVisible: true },
  { uid: 'NO_ACCESS', name: 'No access', isVisible: true },
  // The basic member role is registered too, but hidden with RBAC.
  { uid: 'MEMBER', name: 'Member', isVisible: false },
]

test('summarises the workspace roles with basic members as builders', async () => {
  const workspace = {
    id: 12,
    name: 'Widelab',
    users: [
      { user_id: 1, permissions: 'ADMIN' },
      { user_id: 2, permissions: 'BUILDER' },
      { user_id: 3, permissions: 'MEMBER' },
      { user_id: 4, permissions: 'NO_ACCESS' },
    ],
    _: { roles },
  }
  const wrapper = await mountSuspended(ScopeInheritedAccess, {
    props: { workspace, scopeTypeName: 'table' },
    global: {
      mocks: {
        $t: (key, params) =>
          key === 'shareScope.roleCount'
            ? `${params.count} ${params.role}`
            : key,
      },
      stubs: { Context: true, Avatar: true, 'nuxt-link': true },
    },
  })
  try {
    expect(
      wrapper.find('.invite-list__subtitle').text().replace(/\s+/g, ' ')
    ).toBe('1 Admin • 2 Builder')
  } finally {
    wrapper.unmount()
  }
})
