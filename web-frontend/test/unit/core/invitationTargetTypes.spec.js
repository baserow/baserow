import { describe, expect, test, vi } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import { WorkspaceInvitationTargetType } from '@baserow/modules/core/invitationTargetTypes'

describe('WorkspaceInvitationTargetType', () => {
  test('offers the visible workspace roles and sends to the core endpoint', async () => {
    const testApp = new TestApp()
    const mockServer = testApp.mockServer
    const invitation = { id: 1, workspace: 1, email: 'test@example.com' }
    mockServer.mock
      .onPost('/workspaces/invitations/workspace/1/')
      .reply(200, invitation)
    const busEmit = vi.spyOn(testApp.getApp().$bus, '$emit')

    try {
      const targetType = testApp
        .getRegistry()
        .get('invitationTarget', 'workspace')
      expect(targetType).toBeInstanceOf(WorkspaceInvitationTargetType)

      const workspace = {
        id: 1,
        _: {
          roles: [
            { uid: 'ADMIN', isVisible: true },
            { uid: 'HIDDEN', isVisible: false },
          ],
        },
      }
      expect(targetType.getRoles(workspace, { type: 'workspace' })).toEqual([
        { uid: 'ADMIN', isVisible: true },
      ])
      expect(targetType.getTitle(workspace, { type: 'workspace' })).toBeNull()
      expect(
        targetType.getSubtitle(workspace, { type: 'workspace' })
      ).toBeNull()

      const result = await targetType.sendInvitation(
        workspace,
        { type: 'workspace' },
        {
          email: 'test@example.com',
          permissions: 'ADMIN',
          captchaToken: 'a-token',
        },
        'http://localhost/workspace-invitation'
      )

      expect(result).toEqual(invitation)
      const body = JSON.parse(mockServer.mock.history.post[0].data)
      expect(body.email).toBe('test@example.com')
      expect(body.permissions).toBe('ADMIN')
      expect(body.base_url).toBe('http://localhost/workspace-invitation')
      expect(body.captcha_token).toBe('a-token')
      expect(busEmit).toHaveBeenCalledWith('invite-submitted', invitation)
    } finally {
      vi.restoreAllMocks()
      await testApp.afterEach()
    }
  })
})
