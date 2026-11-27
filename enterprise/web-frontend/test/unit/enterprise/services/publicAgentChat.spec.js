import { describe, expect, test, vi } from 'vitest'

import PublicAgentChatService from '@baserow_enterprise/services/publicAgentChat'

describe('public agent chat service', () => {
  test('encodes the slug from the page URL as one path segment', () => {
    const client = { get: vi.fn(), post: vi.fn() }
    const service = PublicAgentChatService(client)
    const slug = '../x?y#z'
    const encoded = '..%2Fx%3Fy%23z'

    service.getInfo(slug)
    service.authorize(slug, 'secret')
    service.startConversation(slug, {})
    service.getConversation(slug, 'token')
    service.sendMessage(slug, {}, 'token')
    service.stop(slug, 'token')
    service.stream(slug, 'run', null, 'token', () => {}, null)

    const paths = [...client.get.mock.calls, ...client.post.mock.calls].map(
      ([path]) => path
    )
    expect(paths.sort()).toEqual(
      [
        `/agent/public-chat/${encoded}/`,
        `/agent/public-chat/${encoded}/auth/`,
        `/agent/public-chat/${encoded}/conversations/`,
        `/agent/public-chat/${encoded}/conversation/`,
        `/agent/public-chat/${encoded}/conversation/messages/`,
        `/agent/public-chat/${encoded}/conversation/stop/`,
        `/chat-runs/agent-public-chat/${encoded}/stream/`,
      ].sort()
    )
  })
})
