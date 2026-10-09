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

test('manages child agent roles without requiring application role access', async () => {
  const client = {
    get: vi.fn().mockResolvedValue({ data: [] }),
    post: vi.fn().mockResolvedValue({ data: [{ id: 1 }] }),
  }
  const application = { id: 20, type: 'agent_builder', workspace }
  const agentDefinition = { id: 40, name: 'Support', agent_builder_id: 20 }
  const wrapper = await mountSuspended(MemberRolesModal, {
    props: { application, agentDefinition },
    global: {
      mocks: {
        $client: client,
        $featureFlagIsEnabled: () => false,
        $hasPermission: (operation) =>
          operation === 'agent_builder_agent.read_role',
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
          props: ['scopeType', 'scope', 'roleAssignments'],
          template:
            '<div class="role-management" :data-scope="scopeType"><span>{{ scope.name }} ({{ roleAssignments.length }})</span><button class="invite" @click="$emit(\'invite-members\', [{ user_id: 5 }], { uid: \'BUILDER\' })">Invite</button></div>',
        },
      },
    },
  })

  try {
    await wrapper.find('.open').trigger('click')
    await flushPromises()
    expect(wrapper.find('.role-management').attributes('data-scope')).toBe(
      'agent_builder_agent'
    )
    expect(client.get).toHaveBeenCalledWith('/role/12/', {
      params: { scope_id: 40, scope_type: 'agent_builder_agent' },
    })
    expect(client.get).not.toHaveBeenCalledWith('/role/12/', {
      params: { scope_id: 20, scope_type: 'application' },
    })

    await wrapper.find('.invite').trigger('click')
    await flushPromises()
    expect(client.post).toHaveBeenCalledWith('/role/12/batch/', {
      items: [
        {
          subject_id: 5,
          subject_type: 'auth.User',
          scope_id: 40,
          scope_type: 'agent_builder_agent',
          role: 'BUILDER',
        },
      ],
    })
    expect(wrapper.find('.role-management').text()).toContain('Support (1)')
  } finally {
    wrapper.unmount()
  }
})
