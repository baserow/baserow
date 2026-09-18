import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import MemberRolesModal from '@baserow_enterprise/components/member-roles/MemberRolesModal'

const workspace = { id: 12, users: [] }

test.each([
  [false, true, false],
  [true, false, false],
  [true, true, true],
])(
  'keeps role management usable with Agent flag=%s, permission=%s, failure=%s',
  async (enabled, allowed, fails) => {
    const notify = vi.fn()
    const client = {
      get: vi.fn((url) => {
        if (url.startsWith('/agents/')) {
          return Promise.reject({ handler: { notifyIf: notify } })
        }
        return Promise.resolve({ data: [] })
      }),
    }
    const wrapper = await mountSuspended(MemberRolesModal, {
      props: { application: { id: 20, type: 'database', workspace } },
      global: {
        mocks: {
          $client: client,
          $featureFlagIsEnabled: () => enabled,
          $hasPermission: (operation) =>
            operation === 'workspace.list_agents' ? allowed : true,
          $store: { getters: { 'workspace/get': () => workspace } },
        },
        stubs: {
          Modal: {
            template:
              '<div><button class="open" @click="$emit(\'show\')">Open</button><slot /></div>',
          },
          Tabs: { template: '<div><slot /></div>' },
          Tab: { template: '<div><slot /></div>' },
          MemberRolesTab: {
            template: '<div class="role-management">Manage roles</div>',
          },
        },
      },
    })
    try {
      await wrapper.find('.open').trigger('click')
      await flushPromises()
      expect(wrapper.find('.role-management').exists()).toBe(true)
      expect(
        client.get.mock.calls.some(([url]) => url.startsWith('/agents/'))
      ).toBe(fails)
      expect(notify).toHaveBeenCalledTimes(fails ? 1 : 0)
    } finally {
      wrapper.unmount()
    }
  }
)
