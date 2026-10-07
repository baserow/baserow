import { TestApp } from '@baserow/test/helpers/testApp'

describe('agent chat channel types', () => {
  let testApp
  let registry

  beforeAll(() => {
    testApp = new TestApp()
    registry = testApp.getRegistry()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('every channel type is registered with a card and a group', () => {
    const types = registry
      .getOrderedList('agentChatChannel')
      .map((type) => type.getType())
    expect(types).toEqual([
      'web',
      'website',
      'slack',
      'email',
      'gmail',
      'outlook',
    ])
    for (const type of registry.getOrderedList('agentChatChannel')) {
      expect(type.cardComponent).not.toBeNull()
      expect(type.draftComponent).not.toBeNull()
      expect(type.group.id).toBeTruthy()
    }
    expect(registry.get('agentChatChannel', 'gmail').group.id).toBe('email')
    expect(registry.get('agentChatChannel', 'slack').group.id).toBe('chat-apps')
  })

  test('the hosted address needs inbound email on the installation', () => {
    const email = registry.get('agentChatChannel', 'email')
    testApp.store.commit('settings/SET_SETTINGS', {
      inbound_email_enabled: false,
    })
    expect(email.isAvailable()).toBe(false)
    expect(email.unavailableReason).toBeTruthy()
    testApp.store.commit('settings/SET_SETTINGS', {
      inbound_email_enabled: true,
    })
    expect(email.isAvailable()).toBe(true)
  })

  test('mailbox channels need an integration before they can be created', () => {
    const gmail = registry.get('agentChatChannel', 'gmail')
    expect(gmail.canCreate({ config: {} })).toBe(false)
    expect(gmail.canCreate({ config: { integration_id: 3 } })).toBe(true)
    expect(gmail.integrationType.getType()).toBe('google')
    expect(
      registry.get('agentChatChannel', 'outlook').integrationType.getType()
    ).toBe('microsoft')
    expect(
      gmail.seedDraft({
        name: 'Mail',
        config: {
          label: 'Agent',
          alias: 'a@b.c',
          allowed_sender_domains: ['x.y'],
        },
      })
    ).toEqual({
      name: 'Mail',
      allowedSenderDomains: 'x.y',
      alias: 'a@b.c',
      label: 'Agent',
    })
  })
})
