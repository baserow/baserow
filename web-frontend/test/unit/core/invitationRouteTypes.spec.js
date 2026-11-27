import { describe, expect, test } from 'vitest'

import {
  EmailInvitationRouteType,
  LinkInvitationRouteType,
} from '@baserow/modules/core/invitationRouteTypes'

describe('LinkInvitationRouteType', () => {
  function createRouteType(
    settings = {
      allow_new_signups: true,
      allow_signups_via_workspace_invitations: false,
    }
  ) {
    const targetTypes = {
      workspace: { supportsInvitationLinks: () => true },
      scope: { supportsInvitationLinks: () => false },
    }
    return new LinkInvitationRouteType({
      app: {
        $registry: { get: (registry, type) => targetTypes[type] },
        $store: { getters: { 'settings/get': settings } },
      },
    })
  }

  test('is only enabled while people can sign up through links', () => {
    const workspace = { id: 42 }
    const target = { type: 'workspace' }
    const enabled = (settings) =>
      createRouteType(settings).isEnabled(workspace, target)

    expect(
      enabled({
        allow_new_signups: true,
        allow_signups_via_workspace_invitations: false,
      })
    ).toBe(true)
    expect(
      enabled({
        allow_new_signups: false,
        allow_signups_via_workspace_invitations: true,
      })
    ).toBe(true)
    expect(
      enabled({
        allow_new_signups: false,
        allow_signups_via_workspace_invitations: false,
      })
    ).toBe(false)
  })

  test('is only enabled for targets that support links', () => {
    const routeType = createRouteType()
    const workspace = { id: 42 }

    expect(routeType.isEnabled(workspace, { type: 'workspace' })).toBe(true)
    expect(routeType.isEnabled(workspace, { type: 'scope' })).toBe(false)
  })
})

describe('EmailInvitationRouteType', () => {
  test('only serves the workspace target', () => {
    const routeType = new EmailInvitationRouteType({ app: {} })
    const workspace = { id: 42 }

    expect(routeType.isEnabled(workspace, { type: 'workspace' })).toBe(true)
    expect(routeType.isEnabled(workspace, { type: 'scope' })).toBe(false)
  })
})
