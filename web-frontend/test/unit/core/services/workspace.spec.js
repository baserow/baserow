import { expect, test, vi } from 'vitest'

import WorkspaceService from '@baserow/modules/core/services/workspace'

test('keeps an invitation link slug inside the invitation link paths', () => {
  const client = { get: vi.fn(), post: vi.fn() }
  const service = WorkspaceService(client)
  const slug = '../../../database/rows/table/42/?'

  service.fetchInvitationLinkBySlug(slug)
  service.joinInvitationLink(slug)

  const encoded = '..%2F..%2F..%2Fdatabase%2Frows%2Ftable%2F42%2F%3F'
  expect(client.get).toHaveBeenCalledWith(
    `/workspaces/invitation-links/slug/${encoded}/`
  )
  expect(client.post).toHaveBeenCalledWith(
    `/workspaces/invitation-links/slug/${encoded}/join/`
  )
})
