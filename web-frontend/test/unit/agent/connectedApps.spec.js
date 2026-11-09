import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import AgentConnectedAppsSection from '@baserow/modules/agent/components/configuration/AgentConnectedAppsSection'

const tool = (name, extra = {}) => ({
  name,
  title: '',
  description: `${name} description`,
  annotations: null,
  enabled: false,
  changes_data: true,
  changed_since_review: false,
  removed: false,
  ...extra,
})

const server = (extra = {}) => ({
  id: 5,
  type: 'mcp_server',
  name: 'Docs',
  url: 'https://mcp.example.com/mcp',
  auth_type: 'header',
  auth_header_name: 'Authorization',
  has_auth_header_value: true,
  tools: [],
  ...extra,
})

const inBody = (selector) => [...document.body.querySelectorAll(selector)]
const buttonInBody = (text) =>
  inBody('.modal__box button').find((button) =>
    button.textContent.includes(text)
  )
const inputInModal = (label) =>
  inBody('.modal__box .control')
    .find((group) => group.textContent.includes(label))
    .querySelector('input')
const type = (input, value) => {
  input.value = value
  input.dispatchEvent(new Event('input'))
}
const body = (request) => JSON.parse(request.data)

describe('Agent connected apps', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountSection = (editable = true) =>
    testApp.mount(AgentConnectedAppsSection, {
      props: { editable },
      global: {
        provide: { agentApplication: ref({ id: 10, name: 'Helper' }) },
      },
    })

  test('lists only MCP servers, with how many tools are on or changed', async () => {
    testApp.mock.onGet(/application\/10\/integrations/).reply(200, [
      server({ tools: [tool('a', { enabled: true }), tool('b')] }),
      server({
        id: 6,
        name: 'Tracker',
        tools: [tool('c', { changed_since_review: true })],
      }),
      { id: 7, type: 'local_baserow', name: 'Other' },
    ])
    const wrapper = await mountSection()
    await flushPromises()

    const servers = wrapper.findAll('.agent-connected-apps__server')
    expect(servers.map((item) => item.text())).toEqual([
      expect.stringContaining('Docs'),
      expect.stringContaining('Tracker'),
    ])
    expect(servers[0].text()).toContain('agent.toolsOn')
    expect(servers[1].text()).toContain('agent.connectedAppChanged')
  })

  test('connecting an app lists its tools for review, then saves the choice', async () => {
    testApp.mock.onGet(/application\/10\/integrations/).reply(200, [])
    testApp.mock
      .onPost(/application\/10\/integrations/)
      .reply(200, server({ has_auth_header_value: true }))
    testApp.mock
      .onPost('/integrations/mcp/5/refresh-tools/')
      .reply(200, server({ tools: [tool('search'), tool('delete')] }))
    testApp.mock
      .onPatch('/integrations/mcp/5/tools/')
      .reply(200, server({ tools: [tool('search', { enabled: true })] }))
    const wrapper = await mountSection()
    await flushPromises()

    await wrapper.get('.agent-connected-apps__add').trigger('click')
    await flushPromises()
    buttonInBody('agent.connectedAppAuthHeader').click()
    await flushPromises()
    type(inputInModal('agent.connectedAppName'), 'Docs')
    type(inputInModal('agent.connectedAppUrl'), 'https://mcp.example.com/mcp')
    type(inputInModal('agent.connectedAppHeaderValue'), 'Bearer secret')
    buttonInBody('agent.connectedAppConnect').click()
    await flushPromises()

    expect(body(testApp.mock.history.post[0])).toEqual({
      type: 'mcp_server',
      name: 'Docs',
      url: 'https://mcp.example.com/mcp',
      auth_type: 'header',
      auth_header_name: 'Authorization',
      auth_header_value: 'Bearer secret',
    })
    expect(testApp.mock.history.post[1].url).toBe(
      '/integrations/mcp/5/refresh-tools/'
    )

    // New tools start off; turn on the first one and mark it as a read.
    const rows = inBody('.agent-mcp-tools__columns').slice(1)
    expect(rows).toHaveLength(2)
    const [changesData, allow] = rows[0].querySelectorAll('.checkbox')
    allow.click()
    changesData.click()
    await flushPromises()
    buttonInBody('agent.toolsDone').click()
    await flushPromises()

    expect(body(testApp.mock.history.patch[0])).toEqual({
      tools: [
        { name: 'search', enabled: true, changes_data: false },
        { name: 'delete', enabled: false, changes_data: true },
      ],
    })
    expect(wrapper.text()).toContain('agent.toolsOn')
  })

  test('changing the URL asks for the credential again', async () => {
    testApp.mock.onGet(/application\/10\/integrations/).reply(200, [server()])
    const wrapper = await mountSection()
    await flushPromises()

    await wrapper
      .get('button[aria-label="agent.connectedAppEdit"]')
      .trigger('click')
    await flushPromises()
    type(inputInModal('agent.connectedAppUrl'), 'https://other.example.com/mcp')
    buttonInBody('action.save').click()
    await flushPromises()

    expect(testApp.mock.history.patch).toHaveLength(0)
    expect(
      inBody('.modal__box .control').find((group) =>
        group.textContent.includes('agent.connectedAppHeaderValueRequired')
      )
    ).toBeTruthy()
  })

  test('an unreachable server is explained in the tools modal', async () => {
    testApp.mock
      .onGet(/application\/10\/integrations/)
      .reply(200, [server({ tools: [tool('search')] })])
    testApp.mock.onPost('/integrations/mcp/5/refresh-tools/').reply(400, {
      error: 'ERROR_MCP_SERVER_UNREACHABLE',
      detail: 'The MCP server could not be reached.',
    })
    const wrapper = await mountSection()
    await flushPromises()

    await wrapper
      .findAll('.agent-connected-apps__server button')[0]
      .trigger('click')
    await flushPromises()
    buttonInBody('agent.connectedAppRefresh').click()
    await flushPromises()

    expect(
      document.body.querySelector('.modal__box .alert').textContent
    ).toContain('agent.connectedAppUnreachable')
  })

  test('viewers see the apps but cannot add or edit them', async () => {
    testApp.mock.onGet(/application\/10\/integrations/).reply(200, [server()])
    const wrapper = await mountSection(false)
    await flushPromises()

    expect(wrapper.find('.agent-connected-apps__add').exists()).toBe(false)
    expect(
      wrapper.find('button[aria-label="agent.connectedAppEdit"]').exists()
    ).toBe(false)
  })

  describe('signing in with OAuth', () => {
    let popup

    beforeEach(() => {
      popup = { location: {}, closed: false, close: vi.fn() }
      vi.spyOn(window, 'open').mockReturnValue(popup)
    })

    afterEach(() => {
      vi.restoreAllMocks()
    })

    const oauthServer = (extra = {}) =>
      server({
        auth_type: 'oauth',
        has_auth_header_value: false,
        oauth_connected: false,
        ...extra,
      })

    const createWithOAuth = async (wrapper) => {
      await wrapper.get('.agent-connected-apps__add').trigger('click')
      await flushPromises()
      type(inputInModal('agent.connectedAppName'), 'Linear')
      type(inputInModal('agent.connectedAppUrl'), 'https://mcp.example.com/mcp')
      buttonInBody('agent.connectedAppSignIn').click()
      await flushPromises()
    }

    test('connecting opens the provider in a popup, then lists the tools', async () => {
      let connected = false
      testApp.mock
        .onGet(/application\/10\/integrations/)
        .reply(() => [
          200,
          connected ? [oauthServer({ oauth_connected: true })] : [],
        ])
      testApp.mock
        .onPost(/application\/10\/integrations/)
        .reply(200, oauthServer())
      testApp.mock.onPost('/integrations/mcp/5/oauth/start/').reply(200, {
        authorization_url: 'https://auth.example.com/authorize?x=1',
      })
      testApp.mock
        .onPost('/integrations/mcp/5/refresh-tools/')
        .reply(
          200,
          oauthServer({ oauth_connected: true, tools: [tool('search')] })
        )
      const wrapper = await mountSection()
      await flushPromises()

      await createWithOAuth(wrapper)

      // The popup opens on the click itself, before any request.
      expect(window.open).toHaveBeenCalledTimes(1)
      expect(body(testApp.mock.history.post[0])).toMatchObject({
        auth_type: 'oauth',
        oauth_client_id: '',
      })
      expect(popup.location.href).toBe('https://auth.example.com/authorize?x=1')

      // The provider redirects back, Baserow stores the tokens, the popup closes.
      connected = true
      popup.closed = true
      await vi.waitFor(() =>
        expect(
          inBody('.modal__box .agent-tool-permissions__tool')
        ).toHaveLength(1)
      )
      expect(testApp.mock.history.post.at(-1).url).toBe(
        '/integrations/mcp/5/refresh-tools/'
      )
    })

    test('a closed popup without an account explains it and keeps the server', async () => {
      testApp.mock
        .onGet(/application\/10\/integrations/)
        .reply(200, [oauthServer()])
      testApp.mock
        .onPost(/application\/10\/integrations/)
        .reply(200, oauthServer())
      testApp.mock
        .onPost('/integrations/mcp/5/oauth/start/')
        .reply(200, { authorization_url: 'https://auth.example.com/authorize' })
      const wrapper = await mountSection()
      await flushPromises()

      vi.useFakeTimers({ shouldAdvanceTime: true })
      await createWithOAuth(wrapper)
      popup.closed = true
      // Baserow keeps checking for a while, in case the provider cut the popup
      // off from it while the editor was still signing in.
      await vi.advanceTimersByTimeAsync(125000)

      await vi.waitFor(() =>
        expect(
          document.body.querySelector('.modal__box .alert')?.textContent
        ).toContain('agent.connectedAppSignInFailed')
      )
      expect(inBody('.modal__box h2')[0].textContent).toContain(
        'agent.connectedAppEditTitle'
      )
      vi.useRealTimers()
    })

    test('a server that does not support OAuth says why', async () => {
      testApp.mock.onGet(/application\/10\/integrations/).reply(200, [])
      testApp.mock
        .onPost(/application\/10\/integrations/)
        .reply(200, oauthServer())
      testApp.mock.onPost('/integrations/mcp/5/oauth/start/').reply(400, {
        error: 'ERROR_MCP_OAUTH_FAILED',
        detail: "The MCP server doesn't support OAuth sign-in.",
      })
      const wrapper = await mountSection()
      await flushPromises()

      await createWithOAuth(wrapper)

      expect(popup.close).toHaveBeenCalled()
      expect(
        document.body.querySelector('.modal__box .alert').textContent
      ).toContain("doesn't support OAuth sign-in")
    })

    test('a server without an account asks to sign in instead of listing tools', async () => {
      testApp.mock
        .onGet(/application\/10\/integrations/)
        .reply(200, [oauthServer({ tools: [tool('search')] })])
      const wrapper = await mountSection()
      await flushPromises()

      const card = wrapper.get('.agent-connected-apps__server')
      expect(card.text()).toContain('agent.connectedAppNotConnected')
      expect(card.text()).toContain('agent.connectedAppSignIn')
      expect(card.text()).not.toContain('agent.connectedAppTools')
    })
  })
})
