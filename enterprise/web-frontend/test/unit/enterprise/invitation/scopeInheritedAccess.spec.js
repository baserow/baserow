import { mountSuspended } from '@nuxt/test-utils/runtime'
import { expect, test } from 'vitest'

import {
  AgentSubjectType,
  UserSubjectType,
} from '@baserow/modules/core/subjectTypes'
import ScopeInheritedAccess from '@baserow_enterprise/components/invitation/ScopeInheritedAccess'
import { TeamSubjectType } from '@baserow_enterprise/subjectTypes'

const roles = [
  { uid: 'ADMIN', name: 'Admin', isVisible: true },
  { uid: 'BUILDER', name: 'Builder', isVisible: true },
  { uid: 'EDITOR', name: 'Editor', isVisible: true },
  { uid: 'VIEWER', name: 'Viewer', isVisible: true },
  { uid: 'NO_ACCESS', name: 'No access', isVisible: true },
  // The basic member role is registered too, but hidden with RBAC.
  { uid: 'MEMBER', name: 'Member', isVisible: false },
]
const workspace = { id: 12, name: 'Widelab', _: { roles } }
const database = { id: 30, name: 'CRM' }
const table = { id: 20, name: 'Deals' }
const view = { id: 40, name: 'Q4 pipeline' }

const access = (subjectType, subjectId, role, sourceScopeType, sourceId) => ({
  subject_type: subjectType,
  subject_id: subjectId,
  role,
  source_scope_type: sourceScopeType,
  source_scope_id: sourceId,
  through_teams: false,
  teams: [],
})

const targetType = {
  getScopeTypeName: (scopeType) =>
    ({ application: 'Database', database_table: 'Table' })[scopeType] || 'View',
}

async function mountSummary(
  target,
  effectiveAccess,
  { directKeys = [], canReadRoles = true, stubs = {} } = {}
) {
  const app = {}
  const subjectTypes = [
    new UserSubjectType({ app }),
    new TeamSubjectType({ app }),
    new AgentSubjectType({ app }),
  ]
  return await mountSuspended(ScopeInheritedAccess, {
    props: { workspace, target, targetType, effectiveAccess, directKeys },
    global: {
      mocks: {
        // Named parameters always come second, the plural count third.
        $t: (key, params = {}) => {
          if (key === 'shareScope.roleCount') {
            return `${params.count} ${params.role}`
          }
          if (key === 'shareScope.agentRoleCount') {
            return `${params.count} ${params.role} agent`
          }
          if (key === 'shareScope.everyoneAt') {
            return `Everyone at ${params.name}`
          }
          if (key === 'shareScope.everyoneWithRoleOn') {
            return `Everyone with a role on ${params.name}`
          }
          return key
        },
        $hasPermission: () => canReadRoles,
        $registry: { getOrderedList: () => subjectTypes },
      },
      stubs: { Context: true, Avatar: true, 'nuxt-link': true, ...stubs },
    },
  })
}

const rows = (wrapper) =>
  wrapper
    .findAll('.invite-list__item')
    .map(
      (row) =>
        `${row.find('.invite-list__name').text()}: ` +
        row.find('.invite-list__subtitle').text().replace(/\s+/g, ' ')
    )

test('counts members and agents per role under the level their role comes from', async () => {
  const wrapper = await mountSummary(
    { type: 'scope', scopeType: 'database_view', scope: view, database, table },
    [
      access('auth.User', 1, 'ADMIN', 'workspace', 12),
      access('auth.User', 2, 'EDITOR', 'workspace', 12),
      access('auth.User', 3, 'EDITOR', 'workspace', 12),
      access('core.Agent', 4, 'VIEWER', 'workspace', 12),
      access('auth.User', 5, 'VIEWER', 'application', 30),
      access('auth.User', 6, 'BUILDER', 'database_table', 20),
      // Given a role on the view itself, so it's direct access.
      access('auth.User', 7, 'EDITOR', 'database_view', 40),
    ]
  )
  try {
    expect(rows(wrapper)).toEqual([
      'Everyone at Widelab: 1 Admin • 2 Editor • 1 Viewer agent',
      'Everyone with a role on CRM: 1 Viewer',
      'Everyone with a role on Deals: 1 Builder',
    ])
  } finally {
    wrapper.unmount()
  }
})

test('leaves out subjects listed as direct access and empty levels', async () => {
  const wrapper = await mountSummary(
    { type: 'scope', scopeType: 'database_table', scope: table, database },
    [
      access('auth.User', 1, 'ADMIN', 'workspace', 12),
      // An admin whose role on the table has no effect, listed as direct access.
      access('auth.User', 2, 'ADMIN', 'workspace', 12),
    ],
    { directKeys: ['auth.User:2'] }
  )
  try {
    expect(rows(wrapper)).toEqual(['Everyone at Widelab: 1 Admin'])
  } finally {
    wrapper.unmount()
  }
})

test('tells when no one else has access', async () => {
  const wrapper = await mountSummary(
    { type: 'scope', scopeType: 'application', scope: database },
    []
  )
  try {
    expect(wrapper.findAll('.invite-list__item')).toHaveLength(0)
    expect(wrapper.text()).toBe('shareScope.noInheritedAccess')
  } finally {
    wrapper.unmount()
  }
})

test('offers to manage the roles of a level above only when they can be read', async () => {
  const target = {
    type: 'scope',
    scopeType: 'database_table',
    scope: table,
    database,
  }
  const effectiveAccess = [access('auth.User', 5, 'VIEWER', 'application', 30)]

  for (const canReadRoles of [true, false]) {
    const wrapper = await mountSummary(target, effectiveAccess, {
      canReadRoles,
    })
    try {
      const [row] = wrapper.vm.rows
      expect(row.canManage).toBe(canReadRoles)
      expect(row.manageTarget).toEqual({
        type: 'scope',
        scopeType: 'application',
        scope: database,
      })
    } finally {
      wrapper.unmount()
    }
  }
})

test('asks to close the dialog when leaving for the members page', async () => {
  const wrapper = await mountSummary(
    { type: 'scope', scopeType: 'database_table', scope: table, database },
    [access('auth.User', 1, 'ADMIN', 'workspace', 12)],
    {
      stubs: {
        Context: {
          template: '<div><slot /></div>',
          methods: { toggle() {}, hide() {} },
        },
        'nuxt-link': {
          emits: ['click'],
          template: '<a class="manage" @click="$emit(\'click\')"><slot /></a>',
        },
      },
    }
  )
  try {
    await wrapper.find('.invite-list__item a').trigger('click')
    await wrapper.find('.manage').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  } finally {
    wrapper.unmount()
  }
})

test('requests navigation to the parent without opening another modal', async () => {
  const wrapper = await mountSummary(
    { type: 'scope', scopeType: 'database_table', scope: table, database },
    [access('auth.User', 5, 'VIEWER', 'application', 30)],
    {
      stubs: {
        Context: {
          template: '<div><slot /></div>',
          methods: { toggle() {}, hide() {} },
        },
      },
    }
  )
  try {
    await wrapper.find('.invite-list__item a').trigger('click')
    await wrapper.find('.context__menu-item-link').trigger('click')
    expect(wrapper.emitted('navigate')).toEqual([
      [{ type: 'scope', scopeType: 'application', scope: database }],
    ])
    expect(wrapper.findComponent({ name: 'InviteModal' }).exists()).toBe(false)
  } finally {
    wrapper.unmount()
  }
})
