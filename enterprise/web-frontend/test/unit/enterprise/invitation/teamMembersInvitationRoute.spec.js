import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'

import {
  AgentSubjectType,
  UserSubjectType,
} from '@baserow/modules/core/subjectTypes'
import TeamMembersInvitationRoute from '@baserow_enterprise/components/invitation/TeamMembersInvitationRoute'
import { TeamSubjectType } from '@baserow_enterprise/subjectTypes'

const workspace = {
  id: 12,
  name: 'Widelab',
  users: [
    { id: 2, user_id: 8, name: 'Mark Delgado', email: 'mark@x.com' },
    { id: 3, user_id: 9, name: 'Jane Roe', email: 'jane@x.com' },
    { id: 4, user_id: 10, name: 'Olga Kim', email: 'olga@x.com' },
  ],
  _: { roles: [{ uid: 'EDITOR', name: 'Editor' }] },
}
const team = { id: 3, name: 'Sales', default_role: 'EDITOR' }
const target = { type: 'team', team }
const teamSubjects = [
  { id: 50, subject_id: 8, subject_type: 'auth.User', team: 3 },
  { id: 51, subject_id: 99, subject_type: 'core.Agent', team: 3 },
]
const teamInvitations = [
  { id: 70, invitation_id: 5, email: 'new@x.com', team_id: 3 },
]
const pick = (type, id) => ({ key: `${type}:${id}`, type, id })
const emailPick = (email) => ({ key: `email:${email}`, type: 'email', email })
const MEMBER_PERMISSIONS = [
  'enterprise.teams.create_subject',
  'enterprise.teams.delete_subject',
  'workspace.list_agents',
]
const ALL_PERMISSIONS = [
  ...MEMBER_PERMISSIONS,
  'workspace.create_invitation',
  'workspace.list_invitations',
]
// What the route asked the picker to do, reset on every mount.
const picker = { removed: [], resets: 0 }

function createRegistry(app) {
  const subjectTypes = [
    new UserSubjectType({ app }),
    new TeamSubjectType({ app }),
    new AgentSubjectType({ app }),
  ]
  return {
    get: (namespace, type) => subjectTypes.find((s) => s.type === type),
    getOrderedList: () => subjectTypes,
  }
}

function apiError(title) {
  return {
    handler: {
      getMessage: () => ({ title, message: '' }),
      handled: vi.fn(),
      notifyIf: vi.fn(),
      isTooManyRequests: () => false,
    },
  }
}

function createClient() {
  return {
    get: vi.fn((url) => {
      if (url === '/teams/3/subjects/') {
        return Promise.resolve({
          data: teamSubjects.map((teamSubject) => ({ ...teamSubject })),
        })
      }
      if (url === '/teams/3/invitations/') {
        return Promise.resolve({
          data: teamInvitations.map((teamInvitation) => ({
            ...teamInvitation,
          })),
        })
      }
      if (url === '/agents/workspace/12/') {
        return Promise.resolve({
          data: { results: [{ id: 4, name: 'Smith' }], next: null },
        })
      }
      return Promise.resolve({ data: [] })
    }),
    post: vi.fn(),
    delete: vi.fn().mockResolvedValue({}),
  }
}

async function mountRoute(
  client,
  {
    agentsEnabled = true,
    permissions = ALL_PERMISSIONS,
    targetType = {},
    routeTarget = target,
  } = {}
) {
  picker.removed = []
  picker.resets = 0
  const bus = { $emit: vi.fn() }
  const hasPermission = (operation) => permissions.includes(operation)
  const app = {
    $client: client,
    $hasPermission: hasPermission,
    $i18n: { t: (key) => ({ 'subjectType.identity': 'Identity' })[key] ?? key },
  }
  const wrapper = await mountSuspended(TeamMembersInvitationRoute, {
    props: { workspace, target: routeTarget, targetType },
    global: {
      mocks: {
        $client: client,
        $bus: bus,
        $hasPermission: hasPermission,
        $featureFlagIsEnabled: () => agentsEnabled,
        $registry: createRegistry(app),
      },
      stubs: {
        CaptchaWidget: {
          template: '<div class="captcha"></div>',
          methods: { reset() {} },
        },
        Error: {
          props: ['error'],
          template:
            '<div class="error">{{ error.visible ? error.title : "" }}</div>',
        },
        InviteInput: {
          name: 'InviteInput',
          props: ['options', 'tabs', 'roles', 'emailDisabledReason'],
          emits: ['add'],
          template:
            '<div class="picker" :data-roles="roles.length">' +
            '<span v-for="option in options" :key="option.key" ' +
            ":class=\"option.disabledReason ? 'taken' : 'offered'\">" +
            '{{ option.name }}</span>' +
            '<span class="tabs">{{ tabs.map((t) => t.value).join(",") }}</span>' +
            '<span class="email-reason">{{ emailDisabledReason }}</span>' +
            '<span class="email-description"><slot name="email-description" /></span>' +
            '</div>',
          methods: {
            remove(item) {
              picker.removed.push(item.key)
            },
            reset() {
              picker.resets += 1
            },
          },
        },
        ScopeAccessList: {
          props: ['items', 'roles'],
          emits: ['role-updated'],
          template:
            '<div class="access">' +
            '<button v-for="item in items" :key="item.key" class="member" ' +
            '@click="$emit(\'role-updated\', item, null)">{{ item.name }}</button>' +
            '</div>',
        },
      },
    },
  })
  await flushPromises()
  return { wrapper, bus }
}

function memberNames(wrapper) {
  return wrapper.findAll('.member').map((member) => member.text())
}

async function clickMember(wrapper, name) {
  await wrapper
    .findAll('.member')
    .find((member) => member.text() === name)
    .trigger('click')
  await flushPromises()
}

test('lists the members and offers the workspace members who are not in the team', async () => {
  const client = createClient()
  const { wrapper } = await mountRoute(client)

  expect(client.get).toHaveBeenCalledWith('/teams/3/subjects/')
  expect(client.get).toHaveBeenCalledWith('/teams/3/invitations/')
  expect(memberNames(wrapper)).toEqual([
    'new@x.com',
    'Mark Delgado',
    'Identity (99)',
  ])
  // A pending address isn't offered to be invited again.
  expect(wrapper.findAll('.taken').map((o) => o.text())).toEqual([
    'Mark Delgado',
    'new@x.com',
  ])
  expect(wrapper.findAll('.offered').map((o) => o.text())).toEqual([
    'Jane Roe',
    'Olga Kim',
    'Smith',
  ])
  expect(wrapper.get('.tabs').text()).toBe('auth.User,core.Agent')
  expect(wrapper.get('.picker').attributes('data-roles')).toBe('0')
  expect(wrapper.get('.email-reason').text()).toBe('')
  expect(wrapper.find('.captcha').exists()).toBe(true)
})

test('tells an invitee which role the team gives them', async () => {
  const { wrapper } = await mountRoute(createClient())
  expect(wrapper.get('.email-description').text()).toBe(
    'teamMembersRoute.inviteEmailDescription'
  )
  expect(wrapper.vm.teamRoleName).toBe('Editor')

  const { wrapper: withoutRole } = await mountRoute(createClient(), {
    routeTarget: { type: 'team', team: { ...team, default_role: null } },
  })
  expect(withoutRole.get('.email-description').text()).toBe(
    'teamMembersRoute.inviteEmailDescriptionNoRole'
  )
})

test('hides email invitations from who can not send or list them', async () => {
  const client = createClient()
  const { wrapper } = await mountRoute(client, {
    permissions: MEMBER_PERMISSIONS,
  })

  expect(client.get).not.toHaveBeenCalledWith('/teams/3/invitations/')
  expect(memberNames(wrapper)).toEqual(['Mark Delgado', 'Identity (99)'])
  expect(wrapper.get('.email-reason').text()).toBe(
    'teamMembersRoute.emailRequiresInvitePermission'
  )
  expect(wrapper.find('.captcha').exists()).toBe(false)
})

test('leaves the agents out while agents are off', async () => {
  const client = createClient()
  const { wrapper } = await mountRoute(client, { agentsEnabled: false })

  expect(client.get).not.toHaveBeenCalledWith(
    '/agents/workspace/12/',
    expect.anything()
  )
  expect(wrapper.get('.tabs').text()).toBe('auth.User')
  expect(wrapper.findAll('.offered').map((o) => o.text())).toEqual([
    'Jane Roe',
    'Olga Kim',
  ])
  // A member who isn't listed can still be removed.
  expect(memberNames(wrapper)).toContain('Identity (99)')
})

test('adds the picks one after the other and keeps what failed picked', async () => {
  const client = createClient()
  client.post
    .mockResolvedValueOnce({
      data: { id: 60, subject_id: 9, subject_type: 'auth.User', team: 3 },
    })
    .mockRejectedValueOnce(apiError('Could not add'))
  const { wrapper, bus } = await mountRoute(client)

  wrapper
    .findComponent({ name: 'InviteInput' })
    .vm.$emit('add', [pick('auth.User', 9), pick('core.Agent', 4)], null)
  await flushPromises()

  expect(client.post.mock.calls).toEqual([
    ['/teams/3/subjects/', { subject_id: 9, subject_type: 'auth.User' }],
    ['/teams/3/subjects/', { subject_id: 4, subject_type: 'core.Agent' }],
  ])
  expect(picker.removed).toEqual(['auth.User:9'])
  expect(picker.resets).toBe(0)
  expect(wrapper.get('.error').text()).toBe('Could not add')
  expect(memberNames(wrapper)).toContain('Jane Roe')
  expect(bus.$emit).toHaveBeenCalledWith('team-members-updated', 3)
})

test('invites the typed addresses after adding the members', async () => {
  const client = createClient()
  client.post.mockResolvedValue({
    data: { id: 60, subject_id: 9, subject_type: 'auth.User', team: 3 },
  })
  const targetType = {
    sendInvitation: vi
      .fn()
      .mockResolvedValueOnce({
        id: 71,
        invitation_id: 6,
        email: 'a@x.com',
        team_id: 3,
      })
      .mockRejectedValueOnce(apiError('Could not invite')),
  }
  const { wrapper } = await mountRoute(client, { targetType })

  wrapper
    .findComponent({ name: 'InviteInput' })
    .vm.$emit(
      'add',
      [emailPick('a@x.com'), pick('auth.User', 9), emailPick('b@x.com')],
      null
    )
  await flushPromises()

  expect(client.post).toHaveBeenCalledTimes(1)
  expect(targetType.sendInvitation.mock.calls).toEqual([
    [
      workspace,
      target,
      { email: 'a@x.com', permissions: null, captchaToken: '' },
    ],
    [
      workspace,
      target,
      { email: 'b@x.com', permissions: null, captchaToken: '' },
    ],
  ])
  // What failed stays picked, the rest left the input.
  expect(picker.removed).toEqual(['auth.User:9', 'email:a@x.com'])
  expect(picker.resets).toBe(0)
  expect(wrapper.get('.error').text()).toBe('Could not invite')
  expect(memberNames(wrapper)).toEqual([
    'new@x.com',
    'a@x.com',
    'Mark Delgado',
    'Identity (99)',
    'Jane Roe',
  ])
})

test('revokes a pending invitation right away', async () => {
  const client = createClient()
  const { wrapper, bus } = await mountRoute(client)

  await clickMember(wrapper, 'new@x.com')

  expect(client.delete).toHaveBeenCalledWith('/teams/3/invitations/70/')
  expect(memberNames(wrapper)).toEqual(['Mark Delgado', 'Identity (99)'])
  expect(bus.$emit).not.toHaveBeenCalled()
})

test('puts a pending invitation back when revoking it fails', async () => {
  const client = createClient()
  client.delete.mockRejectedValue(apiError('Could not revoke'))
  const { wrapper } = await mountRoute(client)

  await clickMember(wrapper, 'new@x.com')

  expect(memberNames(wrapper)).toEqual([
    'new@x.com',
    'Mark Delgado',
    'Identity (99)',
  ])
})

test('clears the input once every pick was added', async () => {
  const client = createClient()
  client.post.mockResolvedValue({
    data: { id: 60, subject_id: 9, subject_type: 'auth.User', team: 3 },
  })
  const { wrapper } = await mountRoute(client)

  wrapper
    .findComponent({ name: 'InviteInput' })
    .vm.$emit('add', [pick('auth.User', 9)], null)
  await flushPromises()

  expect(picker.removed).toEqual(['auth.User:9'])
  expect(picker.resets).toBe(1)
  expect(wrapper.get('.error').text()).toBe('')
})

test('removes a member right away', async () => {
  const client = createClient()
  const { wrapper, bus } = await mountRoute(client)

  await clickMember(wrapper, 'Mark Delgado')

  expect(client.delete).toHaveBeenCalledWith('/teams/3/subjects/50/')
  expect(memberNames(wrapper)).toEqual(['new@x.com', 'Identity (99)'])
  expect(bus.$emit).toHaveBeenCalledWith('team-members-updated', 3)
})

test('puts a member back when removing them fails', async () => {
  const client = createClient()
  client.delete.mockRejectedValue(apiError('Could not remove'))
  const { wrapper, bus } = await mountRoute(client)

  await clickMember(wrapper, 'Mark Delgado')

  expect(memberNames(wrapper)).toEqual([
    'new@x.com',
    'Mark Delgado',
    'Identity (99)',
  ])
  expect(bus.$emit).not.toHaveBeenCalled()
})
