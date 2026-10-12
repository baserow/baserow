import { describe, expect, test, vi } from 'vitest'

import { ScopeInvitationTargetType } from '@baserow_enterprise/invitationTargetTypes'
import { MemberInvitationRouteType } from '@baserow_enterprise/invitationRouteTypes'

const roles = [
  {
    uid: 'ADMIN',
    isVisible: true,
    allowedScopeTypes: ['workspace', 'application', 'database_table'],
    allowedSubjectTypes: ['auth.User', 'baserow_enterprise.Team'],
  },
  { uid: 'VIEWER', isVisible: true },
  { uid: 'NO_ACCESS', isVisible: true },
  {
    uid: 'NO_ROLE_LOW_PRIORITY',
    isVisible: true,
    allowedScopeTypes: ['workspace'],
    allowedSubjectTypes: ['auth.User'],
  },
]
const workspace = { id: 12, _: { roles } }

function createApp(client = {}) {
  return {
    $client: client,
    $i18n: {
      t: (key, params) => {
        if (key === 'scopeInvitationTarget.title') {
          return `Share ${params.name}`
        }
        if (key === 'scopeInvitationTarget.table') {
          return 'Table'
        }
        return params ? `${key}:${JSON.stringify(params)}` : key
      },
    },
    $hasFeature: vi.fn().mockReturnValue(true),
    $store: {
      getters: {
        'application/get': (id) => ({ id, name: 'Project Tracker' }),
      },
    },
    $registry: {
      exists: (namespace, type) => type === 'automation',
      get: () => ({ getName: () => 'Automation' }),
    },
  }
}

describe('ScopeInvitationTargetType', () => {
  test('offers only the roles a user can hold on the scope', () => {
    const targetType = new ScopeInvitationTargetType({ app: createApp() })

    expect(
      targetType
        .getRoles(workspace, { scopeType: 'database_view' })
        .map(({ uid }) => uid)
    ).toEqual(['VIEWER'])
    expect(
      targetType
        .getRoles(workspace, { scopeType: 'database_table' })
        .map(({ uid }) => uid)
    ).toEqual(['ADMIN', 'VIEWER'])
  })

  test('titles the modal after the object and tells where it lives', () => {
    const targetType = new ScopeInvitationTargetType({ app: createApp() })
    const target = {
      scopeType: 'database_table',
      scope: { id: 5, name: 'Customers', database_id: 3 },
    }

    expect(targetType.getTitle({ name: 'Widelab' }, target)).toBe(
      'Share Customers'
    )
    expect(targetType.getSubtitle({ name: 'Widelab' }, target)).toBe(
      'Widelab / Project Tracker / Customers • Table'
    )
  })

  test('names an application after its type', () => {
    const targetType = new ScopeInvitationTargetType({ app: createApp() })
    const application = { id: 3, name: 'Nightly sync', type: 'automation' }

    expect(
      targetType.getSubtitle(
        { name: 'Widelab' },
        { scopeType: 'application', scope: application }
      )
    ).toBe('Widelab / Nightly sync • Automation')
    expect(targetType.getScopeTypeName('application', application)).toBe(
      'Automation'
    )
    // An unregistered type falls back to the generic word.
    expect(
      targetType.getScopeTypeName('application', { type: 'unknown' })
    ).toBe('scopeInvitationTarget.application')
  })

  test('sends a scoped invitation through the role endpoint', async () => {
    const client = { post: vi.fn().mockResolvedValue({ data: { id: 3 } }) }
    const targetType = new ScopeInvitationTargetType({ app: createApp(client) })

    const result = await targetType.sendInvitation(
      workspace,
      { scopeType: 'database_table', scope: { id: 5 } },
      { email: 'foo@bar.com', permissions: 'VIEWER', captchaToken: '' },
      'http://localhost/workspace-invitation'
    )

    expect(result).toEqual({ id: 3 })
    expect(client.post).toHaveBeenCalledWith('/role/12/invitations/', {
      email: 'foo@bar.com',
      role: 'VIEWER',
      scope_id: 5,
      scope_type: 'database_table',
      base_url: 'http://localhost/workspace-invitation',
    })
  })
})

describe('MemberInvitationRouteType', () => {
  test('is only enabled for scope targets with the RBAC feature', () => {
    const app = createApp()
    const routeType = new MemberInvitationRouteType({ app })

    expect(routeType.isEnabled(workspace, { type: 'workspace' })).toBe(false)
    expect(routeType.isEnabled(workspace, { type: 'scope' })).toBe(true)
    expect(app.$hasFeature).toHaveBeenCalledWith('RBAC', 12)

    app.$hasFeature.mockReturnValue(false)
    expect(routeType.isEnabled(workspace, { type: 'scope' })).toBe(false)
  })
})
