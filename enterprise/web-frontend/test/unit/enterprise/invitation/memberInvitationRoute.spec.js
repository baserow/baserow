import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'

import MemberInvitationRoute from '@baserow_enterprise/components/invitation/MemberInvitationRoute'

const roles = [
  { uid: 'EDITOR', name: 'Editor', isVisible: true },
  { uid: 'VIEWER', name: 'Viewer', isVisible: true },
]
const workspace = {
  id: 12,
  name: 'Widelab',
  users: [
    { id: 1, user_id: 7, name: 'Current user', email: 'me@x.com' },
    { id: 2, user_id: 8, name: 'Mark Delgado', email: 'mark@x.com' },
    { id: 3, user_id: 9, name: 'Jane Roe', email: 'jane@x.com' },
  ],
  _: { roles },
}
const target = {
  type: 'scope',
  scopeType: 'database_table',
  scope: { id: 20, name: 'Projects' },
}
const subjectType = {
  getDisplayName: (subject) => subject.name,
  isCurrentUser: (subject, userId) => subject.id === userId,
  avatarColor: 'blue',
}
const team = {
  key: 'baserow_enterprise.Team:3',
  type: 'baserow_enterprise.Team',
  id: 3,
}
const emailPick = (email) => ({ key: `email:${email}`, type: 'email', email })
// What the route asked the picker to do, reset on every mount.
const picker = { removed: [], resets: 0 }
// A captcha widget that needs a moment to issue every token, like the real
// one does after a reset.
const captchaWidget = {
  template: '<div></div>',
  emits: ['token'],
  data: () => ({ captchaEnabled: true, issued: 0 }),
  mounted() {
    this.issue()
  },
  methods: {
    issue() {
      const token = `token-${++this.issued}`
      setTimeout(() => this.$emit('token', token), 0)
    },
    reset() {
      this.$emit('token', '')
      this.issue()
    },
  },
}

function createTargetType() {
  return {
    getRoles: () => roles,
    getScopeTypeName: () => 'Table',
    sendInvitation: vi.fn().mockResolvedValue({
      id: 2,
      email: 'new@x.com',
      role: 'EDITOR',
      scope_id: 20,
    }),
  }
}

function createClient() {
  return {
    get: vi.fn((url) => {
      if (url === '/role/12/invitations/') {
        return Promise.resolve({
          data: [{ id: 1, email: 'olga@x.com', role: 'EDITOR', scope_id: 20 }],
        })
      }
      if (url === '/role/12/') {
        return Promise.resolve({
          data: [
            {
              id: 5,
              subject_type: 'auth.User',
              subject: { id: 8, name: 'Mark Delgado', email: 'mark@x.com' },
              role: 'VIEWER',
              scope_id: 20,
              scope_type: 'database_table',
            },
            {
              id: 7,
              subject_type: 'core.Agent',
              subject: { id: 4, name: 'Smith' },
              role: 'VIEWER',
              scope_id: 20,
              scope_type: 'database_table',
            },
          ],
        })
      }
      if (url === '/agents/workspace/12/') {
        return Promise.resolve({
          data: {
            results: [
              { id: 4, name: 'Smith' },
              { id: 5, name: 'Neo' },
            ],
            next: null,
          },
        })
      }
      return Promise.resolve({ data: [] })
    }),
    post: vi.fn().mockResolvedValue({
      data: [
        {
          id: 6,
          subject_type: 'baserow_enterprise.Team',
          subject: { id: 3, name: 'Management', subject_count: 2 },
          role: 'EDITOR',
          scope_id: 20,
          scope_type: 'database_table',
        },
      ],
    }),
    patch: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue({}),
  }
}

async function mountRoute(
  client,
  targetType,
  { agentsEnabled = false, captcha = false } = {}
) {
  picker.removed = []
  picker.resets = 0
  const wrapper = await mountSuspended(MemberInvitationRoute, {
    props: { workspace, target, targetType },
    global: {
      mocks: {
        $client: client,
        $featureFlagIsEnabled: () => agentsEnabled,
        $hasPermission: () => true,
        $config: { public: { baserowEmbeddedShareUrl: 'http://localhost' } },
        $store: { getters: { 'auth/getUserId': 7 } },
        $registry: { get: () => subjectType },
      },
      stubs: {
        ShareScopeInput: {
          props: ['users', 'teams', 'agents', 'agentsEnabled', 'pendingEmails'],
          template:
            '<div class="picker">{{ users.map((u) => u.name).join(",") }}</div>' +
            '<div class="picker-agents" :data-enabled="agentsEnabled">' +
            '{{ agents.map((a) => a.name).join(",") }}</div>' +
            '<div class="picker-pending">{{ pendingEmails.join(",") }}</div>',
          methods: {
            reset() {
              picker.resets += 1
            },
            remove(item) {
              picker.removed.push(item.key)
            },
          },
        },
        ScopeAccessList: {
          props: ['items'],
          template:
            '<div class="access">{{ items.map((i) => i.key).join(",") }}</div>',
        },
        ScopeInheritedAccess: { template: '<div class="inherited"></div>' },
        CaptchaWidget: captcha
          ? captchaWidget
          : { template: '<div></div>', methods: { reset() {} } },
      },
    },
  })
  await flushPromises()
  return wrapper
}

test('lists pending invitations first and keeps assigned people out of the picker', async () => {
  const client = createClient()
  const wrapper = await mountRoute(client, createTargetType())
  try {
    // The agent with a role on the table is left out: agents are off.
    expect(wrapper.find('.access').text()).toBe('invitation:1,auth.User:8')
    // Mark already has a role and the current user can't pick themselves.
    expect(wrapper.find('.picker').text()).toBe('Jane Roe')
    expect(wrapper.find('.picker-pending').text()).toBe('olga@x.com')
    expect(wrapper.find('.picker-agents').text()).toBe('')
    expect(wrapper.find('.picker-agents').attributes('data-enabled')).toBe(
      'false'
    )
    expect(client.get).not.toHaveBeenCalledWith(
      '/agents/workspace/12/',
      expect.anything()
    )
    expect(wrapper.find('.inherited').exists()).toBe(true)
  } finally {
    wrapper.unmount()
  }
})

test('lists and offers agents once the agents feature flag is on', async () => {
  const wrapper = await mountRoute(createClient(), createTargetType(), {
    agentsEnabled: true,
  })
  try {
    expect(wrapper.find('.access').text()).toBe(
      'invitation:1,auth.User:8,core.Agent:4'
    )
    // Smith already has a role on the table, so only Neo can still be picked.
    expect(wrapper.find('.picker-agents').text()).toBe('Neo')
    expect(wrapper.find('.picker-agents').attributes('data-enabled')).toBe(
      'true'
    )
  } finally {
    wrapper.unmount()
  }
})

test('adds picked subjects in one request and invites emails one by one', async () => {
  const client = createClient()
  const targetType = createTargetType()
  const wrapper = await mountRoute(client, targetType)
  try {
    await wrapper.vm.add([team, emailPick('new@x.com')], 'EDITOR')
    await flushPromises()

    expect(client.post).toHaveBeenCalledWith('/role/12/batch/', {
      items: [
        {
          subject_id: 3,
          subject_type: 'baserow_enterprise.Team',
          scope_id: 20,
          scope_type: 'database_table',
          role: 'EDITOR',
        },
      ],
    })
    expect(targetType.sendInvitation).toHaveBeenCalledWith(
      workspace,
      target,
      { email: 'new@x.com', permissions: 'EDITOR', captchaToken: '' },
      'http://localhost/workspace-invitation'
    )
    expect(wrapper.find('.access').text()).toBe(
      'invitation:1,invitation:2,auth.User:8,baserow_enterprise.Team:3'
    )
    // The new invitation is pending now, so its address can't be picked again.
    expect(wrapper.find('.picker-pending').text()).toBe('olga@x.com,new@x.com')
    expect(picker.removed).toEqual([
      'baserow_enterprise.Team:3',
      'email:new@x.com',
    ])
    expect(picker.resets).toBe(1)
  } finally {
    wrapper.unmount()
  }
})

test('sends every invitation with a captcha token of its own', async () => {
  const targetType = createTargetType()
  targetType.sendInvitation.mockImplementation(async (w, t, { email }) => ({
    id: email === 'a@x.com' ? 2 : 3,
    email,
    role: 'EDITOR',
    scope_id: 20,
  }))
  const wrapper = await mountRoute(createClient(), targetType, {
    captcha: true,
  })
  try {
    await wrapper.vm.add([emailPick('a@x.com'), emailPick('b@x.com')], 'EDITOR')
    await flushPromises()

    // A token is accepted once, so the second address waited for the token the
    // widget issued after its reset.
    expect(
      targetType.sendInvitation.mock.calls.map(([, , values]) => [
        values.email,
        values.captchaToken,
      ])
    ).toEqual([
      ['a@x.com', 'token-1'],
      ['b@x.com', 'token-2'],
    ])
    expect(wrapper.find('.access').text()).toBe(
      'invitation:1,invitation:2,invitation:3,auth.User:8'
    )
    expect(picker.resets).toBe(1)
  } finally {
    wrapper.unmount()
  }
})

test('keeps what was not added yet picked and tells why when an invitation fails', async () => {
  const client = createClient()
  const targetType = createTargetType()
  const handler = {
    isTooManyRequests: () => false,
    getMessage: () => ({ title: 'Already a member', message: 'Give a role.' }),
    handled: vi.fn(),
  }
  targetType.sendInvitation
    .mockResolvedValueOnce({ id: 2, email: 'a@x.com', role: 'EDITOR' })
    .mockRejectedValueOnce({ handler })
  const wrapper = await mountRoute(client, targetType)
  try {
    await wrapper.vm.add(
      [team, emailPick('a@x.com'), emailPick('b@x.com')],
      'EDITOR'
    )
    await flushPromises()

    // The team and the first address made it, the second is still picked.
    expect(picker.removed).toEqual([
      'baserow_enterprise.Team:3',
      'email:a@x.com',
    ])
    expect(picker.resets).toBe(0)
    expect(wrapper.find('.access').text()).toBe(
      'invitation:1,invitation:2,auth.User:8,baserow_enterprise.Team:3'
    )
    expect(handler.handled).toHaveBeenCalled()
    expect(wrapper.text()).toContain('Already a member')
    expect(wrapper.vm.adding).toBe(false)
  } finally {
    wrapper.unmount()
  }
})

test('changes and revokes roles of invitations and assignments', async () => {
  const client = createClient()
  const wrapper = await mountRoute(client, createTargetType())
  try {
    const items = () => wrapper.find('.access').text()

    await wrapper.vm.updateItemRole(
      { kind: 'invitation', scopedInvitation: { id: 1 } },
      'VIEWER'
    )
    expect(client.patch).toHaveBeenCalledWith('/role/invitations/1/', {
      role: 'VIEWER',
    })

    await wrapper.vm.updateItemRole(
      { kind: 'invitation', scopedInvitation: { id: 1 } },
      null
    )
    await flushPromises()
    expect(client.delete).toHaveBeenCalledWith('/role/invitations/1/')
    expect(items()).toBe('auth.User:8')

    await wrapper.vm.updateItemRole(
      {
        kind: 'auth.User',
        roleAssignment: {
          id: 5,
          subject_type: 'auth.User',
          subject: { id: 8 },
          scope_id: 20,
          scope_type: 'database_table',
        },
      },
      null
    )
    await flushPromises()
    expect(client.post).toHaveBeenCalledWith('/role/12/', {
      subject_id: 8,
      subject_type: 'auth.User',
      scope_id: 20,
      scope_type: 'database_table',
      role: null,
    })
    expect(items()).toBe('')
  } finally {
    wrapper.unmount()
  }
})
