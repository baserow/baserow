import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'

import {
  AgentSubjectType,
  UserSubjectType,
} from '@baserow/modules/core/subjectTypes'
import MemberInvitationRoute from '@baserow_enterprise/components/invitation/MemberInvitationRoute'
import { TeamSubjectType } from '@baserow_enterprise/subjectTypes'

// The roles an invitation can grant, which is every role but no access.
const roles = [
  { uid: 'EDITOR', name: 'Editor', isVisible: true },
  { uid: 'VIEWER', name: 'Viewer', isVisible: true },
]
const noAccess = { uid: 'NO_ACCESS', name: 'No access', isVisible: true }
const workspace = {
  id: 12,
  name: 'Widelab',
  users: [
    { id: 1, user_id: 7, name: 'Current user', email: 'me@x.com' },
    { id: 2, user_id: 8, name: 'Mark Delgado', email: 'mark@x.com' },
    { id: 3, user_id: 9, name: 'Jane Roe', email: 'jane@x.com' },
  ],
  _: { roles: [...roles, noAccess] },
}
const target = {
  type: 'scope',
  scopeType: 'database_table',
  scope: { id: 20, name: 'Projects' },
}
// The registered subject types, with the app they fetch their subjects with.
function createRegistry(app) {
  const subjectTypes = [
    new UserSubjectType({ app }),
    new TeamSubjectType({ app }),
    new AgentSubjectType({ app }),
  ]
  return {
    get: (namespace, type) => subjectTypes.find((s) => s.type === type),
    getOrderedList: () => subjectTypes,
    getAll: () =>
      [{ uid: 'ADMIN' }, ...roles, noAccess].map((role) => ({
        getUid: () => role.uid,
        getDeactivatedClickModal: () => null,
      })),
  }
}
const team = {
  key: 'baserow_enterprise.Team:3',
  type: 'baserow_enterprise.Team',
  id: 3,
}
const emailPick = (email) => ({ key: `email:${email}`, type: 'email', email })
// What the route asked the picker to do, reset on every mount.
const picker = { removed: [], resets: 0 }
// The answer the no access confirmation gives, and what it was asked.
const noAccessModal = { answer: true, asked: [] }
const effectiveAccess = [
  {
    subject_type: 'auth.User',
    subject_id: 9,
    role: 'EDITOR',
    source_scope_type: 'workspace',
    source_scope_id: 12,
    through_teams: false,
    teams: [],
  },
]
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
    getScopeTypeName: (scopeType) =>
      ({ application: 'Database', database_view: 'View' })[scopeType] ||
      'Table',
    sendInvitation: vi.fn().mockResolvedValue({
      id: 2,
      email: 'new@x.com',
      role: 'EDITOR',
      scope_id: 20,
    }),
  }
}

function createClient({
  withAgentAssignment = false,
  assignmentsPerScopeType = {},
} = {}) {
  return {
    get: vi.fn((url, config) => {
      const scopeType = config?.params?.scope_type
      if (url === '/role/12/' && scopeType in assignmentsPerScopeType) {
        return Promise.resolve({ data: assignmentsPerScopeType[scopeType] })
      }
      if (url === '/role/12/effective-access/') {
        return Promise.resolve({ data: effectiveAccess })
      }
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
            ...(withAgentAssignment
              ? [
                  {
                    id: 7,
                    subject_type: 'core.Agent',
                    subject: { id: 4, name: 'Smith' },
                    role: 'VIEWER',
                    scope_id: 20,
                    scope_type: 'database_table',
                  },
                ]
              : []),
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
  {
    canListAgents = false,
    captcha = false,
    canInviteNewUsers = true,
    realList = false,
    routeWorkspace = workspace,
    routeTarget = target,
    canReadParentRoles = true,
  } = {}
) {
  picker.removed = []
  picker.resets = 0
  noAccessModal.answer = true
  noAccessModal.asked = []
  const app = {
    $client: client,
    $hasPermission: (operation) =>
      operation !== 'workspace.list_agents' || canListAgents,
    $i18n: { t: (key) => key },
  }
  const wrapper = await mountSuspended(MemberInvitationRoute, {
    props: { workspace: routeWorkspace, target: routeTarget, targetType },
    global: {
      mocks: {
        $client: client,
        $hasPermission: (operation) => {
          if (operation === 'workspace.create_invitation') {
            return canInviteNewUsers
          }
          if (operation.endsWith('.read_role')) {
            return canReadParentRoles
          }
          return true
        },
        $store: { getters: { 'auth/getUserId': 7 } },
        $registry: createRegistry(app),
      },
      stubs: {
        ShareScopeInput: {
          props: [
            'subjects',
            'pendingEmails',
            'assignedRoles',
            'roles',
            'emailRoleUids',
            'emailDisabledReason',
            'inheritedAdmins',
          ],
          template:
            '<div class="picker" :data-email-disabled-reason="emailDisabledReason">' +
            '{{ subjects["auth.User"].map((u) => u.name).join(",") }}</div>' +
            '<div class="picker-agents" ' +
            ':data-enabled="String(\'core.Agent\' in subjects)">' +
            '{{ (subjects["core.Agent"] || []).map((a) => a.name).join(",") }}' +
            '</div>' +
            '<div class="picker-pending">{{ pendingEmails.join(",") }}</div>' +
            '<div class="picker-assigned">{{ JSON.stringify(assignedRoles) }}</div>' +
            '<div class="picker-admins">{{ JSON.stringify(inheritedAdmins) }}</div>' +
            '<div class="picker-roles">{{ roles.map((r) => r.uid).join(",") }}' +
            '|{{ emailRoleUids.join(",") }}</div>' +
            // What the dialog shows below the input.
            '<slot />',
          methods: {
            reset() {
              picker.resets += 1
            },
            remove(item) {
              picker.removed.push(item.key)
            },
          },
        },
        ScopeAccessList: realList
          ? false
          : {
              props: ['items'],
              template:
                '<div class="access">{{ items.map((i) => i.key).join(",") }}</div>' +
                '<div class="access-roles">{{ items.map((i) => i.key + "=" + ' +
                'i.roles.map((r) => r.uid).join("/")).join(",") }}</div>' +
                '<div class="access-locks">{{ items.map((i) => i.key + "=" + ' +
                'i.roleUid + ":" + (i.helpText || "")).join(",") }}</div>',
            },
        ScopeInheritedAccess: {
          name: 'ScopeInheritedAccess',
          props: ['effectiveAccess', 'directKeys'],
          template:
            '<div class="inherited">{{ effectiveAccess.map((e) => ' +
            'e.subject_type + ":" + e.subject_id).join(",") }}' +
            '|{{ directKeys.join(",") }}</div>',
        },
        ScopeNoAccessModal: {
          template: '<div></div>',
          methods: {
            ask(description) {
              noAccessModal.asked.push(description)
              return Promise.resolve(noAccessModal.answer)
            },
          },
        },
        CaptchaWidget: captcha
          ? captchaWidget
          : { template: '<div></div>', methods: { reset() {} } },
      },
    },
  })
  await flushPromises()
  return wrapper
}

test('lists pending invitations first and tells the picker who already has a role', async () => {
  const client = createClient()
  const wrapper = await mountRoute(client, createTargetType())
  try {
    expect(wrapper.find('.access').text()).toBe('invitation:1,auth.User:8')
    // Everyone but the current user reaches the picker, which lists the ones
    // with a role on the table as such.
    expect(wrapper.find('.picker').text()).toBe('Mark Delgado,Jane Roe')
    expect(wrapper.find('.picker-pending').text()).toBe('olga@x.com')
    expect(wrapper.find('.picker-assigned').text()).toBe(
      '{"auth.User:8":"VIEWER"}'
    )
    expect(wrapper.find('.picker-agents').text()).toBe('')
    expect(wrapper.find('.picker-agents').attributes('data-enabled')).toBe(
      'true'
    )
    expect(client.get).not.toHaveBeenCalledWith(
      '/agents/workspace/12/',
      expect.anything()
    )
    expect(wrapper.find('.inherited').exists()).toBe(true)
    // Members can be given no access on the table, invitations can't.
    expect(wrapper.find('.picker-roles').text()).toBe(
      'EDITOR,VIEWER,NO_ACCESS|EDITOR,VIEWER'
    )
    expect(wrapper.find('.access-roles').text()).toBe(
      'invitation:1=EDITOR/VIEWER,auth.User:8=EDITOR/VIEWER/NO_ACCESS'
    )
  } finally {
    wrapper.unmount()
  }
})

test('explains why a scope admin cannot invite new people', async () => {
  const wrapper = await mountRoute(createClient(), createTargetType(), {
    canInviteNewUsers: false,
  })
  try {
    expect(wrapper.text()).toContain('shareScope.workspaceInvitationRequired')
    expect(
      wrapper.find('.picker').attributes('data-email-disabled-reason')
    ).toBe('shareScope.workspaceInvitationRequired')
    expect(wrapper.find('.picker').text()).toBe('Mark Delgado,Jane Roe')
  } finally {
    wrapper.unmount()
  }
})

test('uses the shared list to change and revoke only a scoped invitation', async () => {
  const client = createClient()
  const wrapper = await mountRoute(client, createTargetType(), {
    realList: true,
  })
  try {
    expect(wrapper.find('.invite-list__items--scrollable').exists()).toBe(true)
    const row = wrapper.find('.invite-list__item')
    expect(row.find('.invite-list__name').text()).toContain('olga@x.com')
    expect(row.find('.invite-list__role > a').text()).toBe('Editor')

    await row.find('.invite-list__role > a').trigger('click')
    await row
      .findAll('.context__menu-item-link')
      .find((link) => link.text().trim() === 'Viewer')
      .trigger('click')
    await flushPromises()
    expect(client.patch).toHaveBeenCalledWith('/role/invitations/1/', {
      role: 'VIEWER',
    })
    expect(row.find('.invite-list__role > a').text()).toBe('Viewer')

    await row.find('.invite-list__role > a').trigger('click')
    await row.find('.context__menu-item-link--delete').trigger('click')
    await flushPromises()
    expect(client.delete.mock.calls).toEqual([['/role/invitations/1/']])
    expect(wrapper.findAll('.invite-list__item')).toHaveLength(1)
    expect(wrapper.find('.invite-list__name').text()).toBe('Mark Delgado')
  } finally {
    wrapper.unmount()
  }
})

test('shows existing scope users, including the current user with a read-only role', async () => {
  const client = createClient()
  const get = client.get.getMockImplementation()
  client.get.mockImplementation(async (url, ...args) => {
    const response = await get(url, ...args)
    if (url !== '/role/12/') {
      return response
    }
    return {
      data: [
        ...response.data,
        {
          id: 8,
          subject_type: 'auth.User',
          subject: { id: 7, name: 'Current user', email: 'me@x.com' },
          role: 'VIEWER',
          scope_id: 20,
          scope_type: 'database_table',
        },
        {
          id: 9,
          subject_type: 'baserow_enterprise.Team',
          subject: { id: 3, name: 'Management', subject_count: 2 },
          role: 'EDITOR',
          scope_id: 20,
          scope_type: 'database_table',
        },
      ],
    }
  })
  const wrapper = await mountRoute(client, createTargetType(), {
    realList: true,
  })
  try {
    const rows = wrapper.findAll('.invite-list__item')
    expect(rows.map((row) => row.find('.invite-list__name').text())).toEqual([
      expect.stringContaining('olga@x.com'),
      'Mark Delgado',
      'Current user',
      expect.stringContaining('Management'),
    ])
    expect(rows[1].find('.invite-list__role > a').text()).toBe('Viewer')
    expect(rows[2].find('.invite-list__role > a').exists()).toBe(false)
    expect(rows[2].find('.invite-list__role > span').text()).toBe('Viewer')
    expect(rows[3].find('.invite-list__role > a').text()).toBe('Editor')
    expect(wrapper.find('.picker').text()).toBe('Mark Delgado,Jane Roe')
  } finally {
    wrapper.unmount()
  }
})

test('lists assigned agents and offers agents when listing is permitted', async () => {
  const wrapper = await mountRoute(
    createClient({ withAgentAssignment: true }),
    createTargetType(),
    {
      canListAgents: true,
    }
  )
  try {
    expect(wrapper.find('.access').text()).toBe(
      'invitation:1,auth.User:8,core.Agent:4'
    )
    expect(wrapper.find('.picker-agents').text()).toBe('Smith,Neo')
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
    expect(targetType.sendInvitation).toHaveBeenCalledWith(workspace, target, {
      email: 'new@x.com',
      permissions: 'EDITOR',
      captchaToken: '',
    })
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

// A workspace with an admin role, where Jane is an admin of the workspace.
const adminRole = { uid: 'ADMIN', name: 'Admin', isVisible: true }
const adminWorkspace = {
  ...workspace,
  users: [
    { ...workspace.users[0], permissions: 'EDITOR' },
    { ...workspace.users[1], permissions: 'EDITOR' },
    { ...workspace.users[2], permissions: 'ADMIN' },
  ],
  _: { roles: [adminRole, ...roles, noAccess] },
}
const database = { id: 30, name: 'CRM', type: 'database' }
const table = { id: 20, name: 'Projects' }
const assignment = (id, subjectType, subject, role, scopeType, scopeId) => ({
  id,
  subject_type: subjectType,
  subject,
  role,
  scope_id: scopeId,
  scope_type: scopeType,
})
const mark = { id: 8, name: 'Mark Delgado', email: 'mark@x.com' }
const jane = { id: 9, name: 'Jane Roe', email: 'jane@x.com' }
const managers = { id: 3, name: 'Management', subject_count: 2 }
const smith = { id: 4, name: 'Smith' }

test('locks the role of admins of the workspace and of the database', async () => {
  const client = createClient({
    assignmentsPerScopeType: {
      // Mark is an admin of the database himself, the team only through its
      // role, which doesn't protect its members.
      application: [
        assignment(1, 'auth.User', mark, 'ADMIN', 'application', 30),
        assignment(
          2,
          'baserow_enterprise.Team',
          managers,
          'ADMIN',
          'application',
          30
        ),
      ],
      database_table: [
        assignment(5, 'auth.User', mark, 'NO_ACCESS', 'database_table', 20),
        assignment(6, 'auth.User', jane, 'VIEWER', 'database_table', 20),
        assignment(
          7,
          'baserow_enterprise.Team',
          managers,
          'NO_ACCESS',
          'database_table',
          20
        ),
      ],
    },
  })
  const wrapper = await mountRoute(client, createTargetType(), {
    routeWorkspace: adminWorkspace,
    routeTarget: { ...target, database },
  })
  try {
    expect(client.get).toHaveBeenCalledWith('/role/12/', {
      params: { scope_id: 30, scope_type: 'application' },
    })
    expect(JSON.parse(wrapper.find('.picker-admins').text())).toEqual({
      'auth.User:8': 'database',
      'auth.User:9': 'common.workspace',
    })
    expect(wrapper.find('.access-roles').text()).toBe(
      'invitation:1=EDITOR/VIEWER,auth.User:8=ADMIN,auth.User:9=ADMIN,' +
        'baserow_enterprise.Team:3=ADMIN/EDITOR/VIEWER/NO_ACCESS'
    )
    expect(wrapper.find('.access-locks').text()).toBe(
      'invitation:1=EDITOR:,' +
        'auth.User:8=ADMIN:shareScope.inheritedAdminHelpText,' +
        'auth.User:9=ADMIN:shareScope.inheritedAdminHelpText,' +
        'baserow_enterprise.Team:3=NO_ACCESS:'
    )
  } finally {
    wrapper.unmount()
  }
})

test('names the outermost level that makes someone an admin of a view', async () => {
  const client = createClient({
    assignmentsPerScopeType: {
      application: [
        assignment(1, 'auth.User', mark, 'ADMIN', 'application', 30),
      ],
      database_table: [
        assignment(2, 'auth.User', mark, 'ADMIN', 'database_table', 20),
        assignment(3, 'core.Agent', smith, 'ADMIN', 'database_table', 20),
      ],
      database_view: [],
    },
  })
  const wrapper = await mountRoute(client, createTargetType(), {
    routeWorkspace: adminWorkspace,
    routeTarget: {
      type: 'scope',
      scopeType: 'database_view',
      scope: { id: 40, name: 'Grid' },
      database,
      table,
    },
  })
  try {
    expect(JSON.parse(wrapper.find('.picker-admins').text())).toEqual({
      'auth.User:8': 'database',
      'auth.User:9': 'common.workspace',
      'core.Agent:4': 'table',
    })
  } finally {
    wrapper.unmount()
  }
})

test('explains the full access of a direct admin of the table only', async () => {
  const client = createClient({
    assignmentsPerScopeType: {
      application: [],
      database_table: [
        assignment(5, 'auth.User', mark, 'ADMIN', 'database_table', 20),
        assignment(
          6,
          'baserow_enterprise.Team',
          managers,
          'ADMIN',
          'database_table',
          20
        ),
      ],
    },
  })
  const wrapper = await mountRoute(client, createTargetType(), {
    routeWorkspace: adminWorkspace,
    routeTarget: { ...target, database },
  })
  try {
    expect(wrapper.find('.access-locks').text()).toBe(
      'invitation:1=EDITOR:,' +
        'auth.User:8=ADMIN:shareScope.scopeAdminHelpText,' +
        'baserow_enterprise.Team:3=ADMIN:'
    )
  } finally {
    wrapper.unmount()
  }
})

test('skips the parent roles the user may not read', async () => {
  const client = createClient()
  const wrapper = await mountRoute(client, createTargetType(), {
    routeWorkspace: adminWorkspace,
    routeTarget: { ...target, database },
    canReadParentRoles: false,
  })
  try {
    expect(client.get).not.toHaveBeenCalledWith('/role/12/', {
      params: { scope_id: 30, scope_type: 'application' },
    })
    // The workspace admins are still known from the workspace itself.
    expect(JSON.parse(wrapper.find('.picker-admins').text())).toEqual({
      'auth.User:9': 'common.workspace',
    })
  } finally {
    wrapper.unmount()
  }
})

test('shows a locked admin role with an explanation in the list', async () => {
  const client = createClient({
    assignmentsPerScopeType: {
      application: [],
      database_table: [
        assignment(6, 'auth.User', jane, 'NO_ACCESS', 'database_table', 20),
      ],
    },
  })
  const wrapper = await mountRoute(client, createTargetType(), {
    routeWorkspace: adminWorkspace,
    routeTarget: { ...target, database },
    realList: true,
  })
  try {
    const rows = wrapper.findAll('.invite-list__item')
    expect(rows[1].find('.invite-list__name').text()).toBe('Jane Roe')
    expect(rows[1].find('.invite-list__role > a').text()).toBe('Admin')
    expect(rows[1].find('.help-icon').exists()).toBe(true)
    expect(rows[0].find('.help-icon').exists()).toBe(false)

    await rows[1].find('.invite-list__role > a').trigger('click')
    const options = rows[1]
      .findAll('.context__menu-item-link')
      .map((link) => link.text().trim())
    expect(options).toContain('Admin')
    expect(options).not.toContain('No access')
  } finally {
    wrapper.unmount()
  }
})

test('summarises who else has access, without those with a direct role', async () => {
  const client = createClient()
  const wrapper = await mountRoute(client, createTargetType())
  try {
    expect(client.get).toHaveBeenCalledWith('/role/12/effective-access/', {
      params: { scope_id: 20, scope_type: 'database_table' },
    })
    expect(wrapper.find('.inherited').text()).toBe('auth.User:9|auth.User:8')

    // Managing the roles of a level above may change who reaches the object.
    wrapper
      .findComponent({ name: 'ScopeInheritedAccess' })
      .vm.$emit('level-roles-managed')
    await flushPromises()
    expect(
      client.get.mock.calls.filter(
        ([url]) => url === '/role/12/effective-access/'
      )
    ).toHaveLength(2)
  } finally {
    wrapper.unmount()
  }
})

test('asks before giving no access and refreshes who else has access', async () => {
  const client = createClient()
  const wrapper = await mountRoute(client, createTargetType())
  const markRow = {
    kind: 'auth.User',
    name: 'Mark Delgado',
    roleUid: 'VIEWER',
    roleAssignment: {
      id: 5,
      subject_type: 'auth.User',
      subject: { id: 8 },
      scope_id: 20,
      scope_type: 'database_table',
    },
  }
  const effectiveAccessFetches = () =>
    client.get.mock.calls.filter(
      ([url]) => url === '/role/12/effective-access/'
    ).length
  try {
    noAccessModal.answer = false
    await wrapper.vm.add([team, emailPick('new@x.com')], 'NO_ACCESS')
    await wrapper.vm.updateItemRole(markRow, 'NO_ACCESS')
    await flushPromises()
    expect(noAccessModal.asked).toEqual([
      'shareScope.noAccessSelectionDescription - 1',
      'shareScope.noAccessDescription',
    ])
    expect(client.post).not.toHaveBeenCalled()
    expect(effectiveAccessFetches()).toBe(1)

    // No other role, nor an invitation, asks first.
    await wrapper.vm.updateItemRole(markRow, 'EDITOR')
    await wrapper.vm.updateItemRole(
      { kind: 'invitation', scopedInvitation: { id: 1 } },
      'VIEWER'
    )
    expect(noAccessModal.asked).toHaveLength(2)

    noAccessModal.answer = true
    await wrapper.vm.updateItemRole(markRow, 'NO_ACCESS')
    await flushPromises()
    expect(client.post).toHaveBeenLastCalledWith('/role/12/', {
      subject_id: 8,
      subject_type: 'auth.User',
      scope_id: 20,
      scope_type: 'database_table',
      role: 'NO_ACCESS',
    })
    expect(effectiveAccessFetches()).toBe(3)
  } finally {
    wrapper.unmount()
  }
})

test('keeps who else has access from the latest request only', async () => {
  const client = createClient()
  const wrapper = await mountRoute(client, createTargetType())
  const deferred = () => {
    let resolve
    const promise = new Promise((resolvePromise) => (resolve = resolvePromise))
    return { promise, resolve }
  }
  const older = deferred()
  const newer = deferred()
  client.get
    .mockImplementationOnce(() => older.promise)
    .mockImplementationOnce(() => newer.promise)
  try {
    wrapper.vm.fetchEffectiveAccess()
    wrapper.vm.fetchEffectiveAccess()
    newer.resolve({ data: [{ ...effectiveAccess[0], subject_id: 2 }] })
    await flushPromises()
    older.resolve({ data: [{ ...effectiveAccess[0], subject_id: 1 }] })
    await flushPromises()

    expect(wrapper.find('.inherited').text()).toBe('auth.User:2|auth.User:8')
  } finally {
    wrapper.unmount()
  }
})
