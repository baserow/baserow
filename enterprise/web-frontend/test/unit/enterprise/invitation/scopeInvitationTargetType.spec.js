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
    $bus: { $emit: vi.fn() },
    $i18n: {
      t: (key, params) => {
        if (key === 'scopeInvitationTarget.title') {
          return `Share ${params.name}`
        }
        if (key === 'scopeInvitationTarget.table') {
          return 'Table'
        }
        if (key === 'scopeInvitationTarget.view') {
          return 'View'
        }
        return params ? `${key}:${JSON.stringify(params)}` : key
      },
    },
    $hasFeature: vi.fn().mockReturnValue(true),
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
    const database = { id: 3, name: 'Project Tracker' }
    const table = { id: 5, name: 'Customers', database_id: 3 }
    const target = { scopeType: 'database_table', scope: table, database }

    expect(targetType.getTitle({ name: 'Widelab' }, target)).toBe(
      'Share Customers'
    )
    expect(targetType.getSubtitle({ name: 'Widelab' }, target)).toBe(
      'Widelab / Project Tracker / Customers • Table'
    )
    expect(
      targetType.getSubtitle(
        { name: 'Widelab' },
        {
          scopeType: 'database_view',
          scope: { id: 9, name: 'Active', table_id: 5 },
          database,
          table,
        }
      )
    ).toBe('Widelab / Project Tracker / Customers / Active • View')
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
    const scopedInvitation = {
      id: 3,
      invitation_id: 8,
      email: 'foo@bar.com',
    }
    const client = {
      post: vi.fn().mockResolvedValue({ data: scopedInvitation }),
    }
    const app = createApp(client)
    const targetType = new ScopeInvitationTargetType({ app })

    const result = await targetType.sendInvitation(
      workspace,
      { scopeType: 'database_table', scope: { id: 5 } },
      { email: 'foo@bar.com', permissions: 'VIEWER', captchaToken: '' }
    )

    expect(result).toEqual(scopedInvitation)
    expect(client.post).toHaveBeenCalledWith('/role/12/invitations/', {
      email: 'foo@bar.com',
      role: 'VIEWER',
      scope_id: 5,
      scope_type: 'database_table',
    })
    // The members page recounts its pending invitations on this event.
    expect(app.$bus.$emit).toHaveBeenCalledWith('invite-submitted', {
      id: 8,
      workspace: 12,
      email: 'foo@bar.com',
    })
  })
})

describe('ScopeInvitationTargetType invitation links', () => {
  const target = {
    scopeType: 'database_table',
    scope: { id: 5, name: 'Sales' },
  }

  test('manages the links of the object through the role endpoints', async () => {
    const link = { id: 4, slug: 'abc', permissions: 'EDITOR', name: '' }
    const client = {
      get: vi.fn().mockResolvedValue({ data: [link] }),
      post: vi.fn().mockResolvedValue({ data: link }),
      patch: vi.fn().mockResolvedValue({ data: { ...link, name: 'Partners' } }),
      delete: vi.fn().mockResolvedValue({}),
    }
    const targetType = new ScopeInvitationTargetType({ app: createApp(client) })

    expect(targetType.supportsInvitationLinks(workspace, target)).toBe(true)

    expect(await targetType.fetchInvitationLinks(workspace, target)).toEqual([
      link,
    ])
    expect(client.get).toHaveBeenCalledWith('/role/12/invitation-links/', {
      params: { scope_id: 5, scope_type: 'database_table' },
    })

    expect(
      await targetType.createInvitationLink(workspace, target, 'EDITOR')
    ).toEqual(link)
    expect(client.post).toHaveBeenCalledWith('/role/12/invitation-links/', {
      name: '',
      permissions: 'EDITOR',
      scope_id: 5,
      scope_type: 'database_table',
    })

    const updated = await targetType.updateInvitationLink(
      workspace,
      target,
      link,
      { name: 'Partners' }
    )
    expect(updated.name).toBe('Partners')
    expect(client.patch).toHaveBeenCalledWith('/role/invitation-links/4/', {
      name: 'Partners',
    })

    await targetType.deleteInvitationLink(workspace, target, link)
    expect(client.delete).toHaveBeenCalledWith('/role/invitation-links/4/')
  })

  test('warns about what a link to the object gives', () => {
    const targetType = new ScopeInvitationTargetType({ app: createApp() })

    expect(targetType.getInvitationLinkAdminWarning(workspace, target)).toBe(
      'scopeInvitationTarget.linkAdminWarning:{"name":"Sales"}'
    )
    expect(targetType.getInvitationLinkDeleteWarning(workspace, target)).toBe(
      'scopeInvitationTarget.linkDeleteWarning:{"name":"Sales"}'
    )
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
