import { describe, expect, test, vi } from 'vitest'

import { TeamInvitationTargetType } from '@baserow_enterprise/invitationTargetTypes'
import { TeamMembersInvitationRouteType } from '@baserow_enterprise/invitationRouteTypes'

const workspace = {
  id: 12,
  name: 'Widelab',
  _: { roles: [{ uid: 'EDITOR', name: 'Editor' }] },
}

function createApp(hasTeams = true) {
  return {
    $hasFeature: vi.fn().mockReturnValue(hasTeams),
    $i18n: {
      t: (key, params) => (params ? `${key}:${JSON.stringify(params)}` : key),
    },
  }
}

describe('TeamInvitationTargetType', () => {
  const targetType = new TeamInvitationTargetType({ app: createApp() })

  test('has no roles to choose, as members get the role of the team', () => {
    expect(targetType.getRoles(workspace, { type: 'team', team: {} })).toEqual(
      []
    )
  })

  test('names the team and where it lives', () => {
    const target = {
      type: 'team',
      team: { id: 3, name: 'Sales', default_role: 'EDITOR' },
    }

    expect(targetType.getTitle(workspace, target)).toBe(
      'teamInvitationTarget.title:{"name":"Sales"}'
    )
    expect(targetType.getSubtitle(workspace, target)).toBe(
      'teamInvitationTarget.subtitleWithRole:{"workspace":"Widelab","role":"Editor"}'
    )
    expect(
      targetType.getSubtitle(workspace, {
        type: 'team',
        team: { ...target.team, default_role: null },
      })
    ).toBe('teamInvitationTarget.subtitle:{"workspace":"Widelab"}')
  })

  test('invites by email to the team', async () => {
    const app = {
      ...createApp(),
      $client: {
        post: vi.fn().mockResolvedValue({
          data: { id: 70, invitation_id: 5, email: 'a@x.com', team_id: 3 },
        }),
      },
      $bus: { $emit: vi.fn() },
    }
    const sender = new TeamInvitationTargetType({ app })

    const teamInvitation = await sender.sendInvitation(
      workspace,
      { type: 'team', team: { id: 3 } },
      { email: 'a@x.com', permissions: null, captchaToken: 'token' }
    )

    expect(app.$client.post).toHaveBeenCalledWith('/teams/3/invitations/', {
      email: 'a@x.com',
      captcha_token: 'token',
    })
    expect(teamInvitation.id).toBe(70)
    // The members page recounts its pending invitations.
    expect(app.$bus.$emit).toHaveBeenCalledWith('invite-submitted', {
      id: 5,
      workspace: 12,
      email: 'a@x.com',
    })
  })

  test('supports links only for who can add members and create links', () => {
    const granted = new Set([
      'enterprise.teams.create_subject',
      'workspace.create_invitation_link',
    ])
    const app = {
      ...createApp(),
      $hasPermission: vi.fn((operation) => granted.has(operation)),
    }
    const linkTarget = new TeamInvitationTargetType({ app })

    expect(linkTarget.supportsInvitationLinks(workspace)).toBe(true)
    expect(app.$hasPermission).toHaveBeenCalledWith(
      'enterprise.teams.create_subject',
      workspace,
      12
    )

    granted.delete('workspace.create_invitation_link')
    expect(linkTarget.supportsInvitationLinks(workspace)).toBe(false)
  })

  test('manages the links of the team without a role', async () => {
    const link = { id: 9, name: 'Fair', slug: 'abc', team_id: 3 }
    const app = {
      ...createApp(),
      $client: {
        get: vi.fn().mockResolvedValue({ data: [link] }),
        post: vi.fn().mockResolvedValue({ data: link }),
        patch: vi.fn().mockResolvedValue({ data: { ...link, name: 'New' } }),
        delete: vi.fn().mockResolvedValue({}),
      },
    }
    const linkTarget = new TeamInvitationTargetType({ app })
    const target = { type: 'team', team: { id: 3 } }

    expect(await linkTarget.fetchInvitationLinks(workspace, target)).toEqual([
      link,
    ])
    expect(app.$client.get).toHaveBeenCalledWith('/teams/3/invitation-links/')

    await linkTarget.createInvitationLink(workspace, target, null)
    expect(app.$client.post).toHaveBeenCalledWith(
      '/teams/3/invitation-links/',
      {}
    )

    const updated = await linkTarget.updateInvitationLink(
      workspace,
      target,
      link,
      { name: 'New' }
    )
    expect(updated.name).toBe('New')
    expect(app.$client.patch).toHaveBeenCalledWith(
      '/teams/3/invitation-links/9/',
      { name: 'New' }
    )

    await linkTarget.deleteInvitationLink(workspace, target, link)
    expect(app.$client.delete).toHaveBeenCalledWith(
      '/teams/3/invitation-links/9/'
    )
  })

  test('shows the role the team gives and asks first for admin teams', () => {
    const team = { id: 3, name: 'Sales', default_role: 'EDITOR' }

    expect(targetType.getInvitationLinkRole(workspace, { team }).name).toBe(
      'Editor'
    )
    expect(
      targetType.getInvitationLinkRole(workspace, {
        team: { ...team, default_role: null },
      })
    ).toBe(null)
    expect(targetType.getInvitationLinkRoleHelpText(workspace, { team })).toBe(
      'teamInvitationTarget.linkRoleHelpText'
    )
    expect(
      targetType.invitationLinkGrantsAdmin(workspace, { team }, null)
    ).toBe(false)
    expect(
      targetType.invitationLinkGrantsAdmin(
        workspace,
        { team: { ...team, default_role: 'ADMIN' } },
        null
      )
    ).toBe(true)
    expect(targetType.getInvitationLinkAdminWarning(workspace, { team })).toBe(
      'teamInvitationTarget.linkAdminWarning:{"name":"Sales"}'
    )
    expect(targetType.getInvitationLinkDeleteWarning(workspace, { team })).toBe(
      'teamInvitationTarget.linkDeleteWarning:{"name":"Sales"}'
    )
  })
})

describe('TeamMembersInvitationRouteType', () => {
  test('is only offered for a team with the teams feature', () => {
    const app = createApp()
    const routeType = new TeamMembersInvitationRouteType({ app })
    const team = { type: 'team', team: { id: 3 } }

    expect(routeType.isEnabled(workspace, team)).toBe(true)
    expect(app.$hasFeature).toHaveBeenCalledWith('TEAMS', 12)
    expect(routeType.isEnabled(workspace, { type: 'workspace' })).toBe(false)
    expect(routeType.isEnabled(workspace, { type: 'scope' })).toBe(false)

    const unlicensed = new TeamMembersInvitationRouteType({
      app: createApp(false),
    })
    expect(unlicensed.isEnabled(workspace, team)).toBe(false)
  })
})
