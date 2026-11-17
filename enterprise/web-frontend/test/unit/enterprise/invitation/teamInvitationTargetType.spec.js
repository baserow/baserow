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

  test('does not invite by email', () => {
    expect(() => targetType.sendInvitation(workspace, {}, {})).toThrow()
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
