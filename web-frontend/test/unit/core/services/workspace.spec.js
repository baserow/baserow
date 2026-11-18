import { expect, test, vi } from 'vitest'

import WorkspaceService from '@baserow/modules/core/services/workspace'

test('keeps an invitation link slug inside the invitation link paths', () => {
  const client = { get: vi.fn(), post: vi.fn() }
  const service = WorkspaceService(client)
  const slug = '../../../database/rows/table/42/?'

  service.fetchInvitationLinkBySlug(slug)
  service.joinInvitationLink(slug)
  service.authInvitationLink(slug, 'correct horse battery')

  const encoded = '..%2F..%2F..%2Fdatabase%2Frows%2Ftable%2F42%2F%3F'
  expect(client.get).toHaveBeenCalledWith(
    `/workspaces/invitation-links/slug/${encoded}/`,
    { headers: {} }
  )
  expect(client.post).toHaveBeenCalledWith(
    `/workspaces/invitation-links/slug/${encoded}/join/`,
    null,
    { headers: {} }
  )
  expect(client.post).toHaveBeenCalledWith(
    `/workspaces/invitation-links/slug/${encoded}/auth/`,
    { password: 'correct horse battery' }
  )
})

test('sends the token of a password protected invitation link', () => {
  const client = { get: vi.fn(), post: vi.fn() }
  const service = WorkspaceService(client)

  service.fetchInvitationLinkBySlug('abc', 'link-token')
  service.joinInvitationLink('abc', 'link-token')

  const headers = { 'Baserow-Invitation-Link-Authorization': 'JWT link-token' }
  expect(client.get).toHaveBeenCalledWith(
    '/workspaces/invitation-links/slug/abc/',
    { headers }
  )
  expect(client.post).toHaveBeenCalledWith(
    '/workspaces/invitation-links/slug/abc/join/',
    null,
    { headers }
  )
})
