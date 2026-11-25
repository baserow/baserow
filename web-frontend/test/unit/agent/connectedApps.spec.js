import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import AgentConnectedAppsSection from '@baserow/modules/agent/components/configuration/AgentConnectedAppsSection'
import { MCP_OAUTH_MESSAGE_TYPE } from '@baserow/modules/agent/constants'
import { registerRealtimeEvents } from '@baserow/modules/builder/realtime'
import { deferredReply } from './helpers'

const tool = (name, extra = {}) => ({
  name,
  title: '',
  description: `${name} description`,
  annotations: null,
  enabled: false,
  ask_first: true,
  changes_data: true,
  changed_since_review: false,
  removed: false,
  definition_hash: `${name}-hash`,
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
const cards = (wrapper) => wrapper.findAll('.agent-mcp-server-card')
const card = (wrapper, index = 0) => cards(wrapper)[index].element
const expand = async (wrapper, index = 0) => {
  card(wrapper, index).querySelector('.agent-action-card__toggle').click()
  await flushPromises()
}
const inputIn = (element, label) =>
  [...element.querySelectorAll('.control')]
    .find((group) => group.textContent.includes(label))
    .querySelector('input')
const buttonIn = (element, text) =>
  [...element.querySelectorAll('button')].find((button) =>
    button.textContent.includes(text)
  )
const openTools = async (wrapper, index = 0) => {
  card(wrapper, index)
    .querySelector('.agent-mcp-server-card__tools-button')
    .click()
  await flushPromises()
}
const addApp = async (wrapper) => {
  await wrapper.get('.agent-connected-apps__add').trigger('click')
  await flushPromises()
  return cards(wrapper).at(-1).element
}
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

    const servers = cards(wrapper)
    expect(servers.map((item) => item.text())).toEqual([
      expect.stringContaining('Docs'),
      expect.stringContaining('Tracker'),
    ])
    expect(servers[0].text()).toContain('agent.toolsOn')
    expect(servers[0].text()).toContain('agent.connectedAppConnected')
    expect(servers[1].text()).toContain('agent.connectedAppChanged')
  })

  test('connecting an app lists its tools for review, then saves the choice', async () => {
    testApp.mock.onGet(/application\/10\/integrations/).reply(200, [])
    testApp.mock
      .onPost(/application\/10\/integrations/)
      .reply(200, server({ has_auth_header_value: true }))
    const discovery = deferredReply()
    testApp.mock
      .onPost('/integrations/mcp/5/refresh-tools/')
      .reply(discovery.reply)
    testApp.mock
      .onPatch('/integrations/mcp/5/tools/')
      .reply(200, server({ tools: [tool('search', { enabled: true })] }))
    const wrapper = await mountSection()
    await flushPromises()

    const draft = await addApp(wrapper)
    buttonIn(draft, 'agent.connectedAppAuthHeader').click()
    await flushPromises()
    type(inputIn(draft, 'agent.connectedAppName'), 'Docs')
    type(inputIn(draft, 'agent.connectedAppUrl'), 'https://mcp.example.com/mcp')
    type(inputIn(draft, 'agent.connectedAppHeaderValue'), 'Bearer secret')
    buttonIn(draft, 'agent.connectedAppConnect').click()
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

    expect(cards(wrapper)).toHaveLength(1)
    const submitButton = card(wrapper).querySelector(
      '.agent-mcp-server-card__actions button:last-child'
    )
    expect(submitButton.textContent).toContain('agent.connectedAppConnect')
    expect(submitButton.disabled).toBe(true)
    discovery.resolve(200, server({ tools: [tool('search'), tool('delete')] }))
    await flushPromises()

    // Preselection is a draft until Save. Bulk selection preserves Ask first.
    const rows = () => inBody('.agent-mcp-tools__tool')
    const enabled = () =>
      rows().map((row) => row.querySelector('input').checked)
    const askFirst = () => rows()[0].querySelectorAll('.checkbox')[1]
    expect(enabled()).toEqual([true, true])
    expect(testApp.mock.history.patch).toHaveLength(0)
    buttonInBody('agent.deselectAllTools').click()
    await flushPromises()
    expect(enabled()).toEqual([false, false])
    expect(askFirst().classList).toContain('checkbox--disabled')
    buttonInBody('agent.selectAllTools').click()
    await flushPromises()
    expect(enabled()).toEqual([true, true])
    rows()[1].querySelector('.checkbox').click()
    await flushPromises()
    askFirst().click()
    await flushPromises()
    buttonInBody('action.save').click()
    await flushPromises()

    expect(body(testApp.mock.history.patch[0])).toEqual({
      tools: [
        {
          name: 'search',
          definition_hash: 'search-hash',
          enabled: true,
          ask_first: false,
        },
        {
          name: 'delete',
          definition_hash: 'delete-hash',
          enabled: false,
          ask_first: true,
        },
      ],
    })
    expect(wrapper.text()).toContain('agent.toolsOn')
    // Saved: the card shows the server and nothing is left to save.
    expect(cards(wrapper)).toHaveLength(1)
    expect(card(wrapper).querySelector('.agent-mcp-server-card__actions')).toBe(
      null
    )
  })

  test('changing the URL asks for the credential again', async () => {
    testApp.mock.onGet(/application\/10\/integrations/).reply(200, [server()])
    const wrapper = await mountSection()
    await flushPromises()

    await expand(wrapper)
    type(
      inputIn(card(wrapper), 'agent.connectedAppUrl'),
      'https://other.example.com/mcp'
    )
    await flushPromises()
    buttonIn(card(wrapper), 'action.save').click()
    await flushPromises()

    expect(testApp.mock.history.patch).toHaveLength(0)
    expect(card(wrapper).textContent).toContain(
      'agent.connectedAppHeaderValueRequired'
    )
  })

  test('a key the server no longer uses is cleared, so the URL can change', async () => {
    testApp.mock.onGet(/application\/10\/integrations/).reply(200, [server()])
    testApp.mock
      .onPatch('integration/5/')
      .reply(200, server({ auth_type: 'none', has_auth_header_value: false }))
    testApp.mock
      .onPost('/integrations/mcp/5/refresh-tools/')
      .reply(200, server())
    const wrapper = await mountSection()
    await flushPromises()

    await expand(wrapper)
    buttonIn(card(wrapper), 'agent.connectedAppAuthNone').click()
    await flushPromises()
    type(
      inputIn(card(wrapper), 'agent.connectedAppUrl'),
      'https://other.example.com/mcp'
    )
    await flushPromises()
    buttonIn(card(wrapper), 'action.save').click()
    await flushPromises()

    expect(body(testApp.mock.history.patch[0])).toEqual({
      url: 'https://other.example.com/mcp',
      auth_type: 'none',
    })
  })

  test("a new URL lists the new server's tools for review", async () => {
    testApp.mock
      .onGet(/application\/10\/integrations/)
      .reply(200, [server({ tools: [tool('old', { enabled: true })] })])
    testApp.mock
      .onPatch('integration/5/')
      .reply(200, server({ url: 'https://other.example.com/mcp' }))
    testApp.mock
      .onPost('/integrations/mcp/5/refresh-tools/')
      .reply(200, server({ tools: [tool('search')] }))
    const wrapper = await mountSection()
    await flushPromises()

    await expand(wrapper)
    type(
      inputIn(card(wrapper), 'agent.connectedAppUrl'),
      'https://other.example.com/mcp'
    )
    await flushPromises()
    type(inputIn(card(wrapper), 'agent.connectedAppHeaderValue'), 'Bearer new')
    await flushPromises()
    buttonIn(card(wrapper), 'action.save').click()
    await flushPromises()

    expect(inBody('.modal__box .agent-tool-permissions__tool')).toHaveLength(1)
    expect(
      inBody('.modal__box .agent-tool-permissions__allow input')[0].checked
    ).toBe(false)
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

    await openTools(wrapper)
    buttonInBody('agent.connectedAppRefresh').click()
    await flushPromises()

    expect(
      document.body.querySelector('.modal__box .alert').textContent
    ).toContain('agent.connectedAppUnreachable')
  })

  test('a refresh that finishes after another server was opened is ignored', async () => {
    let answer
    testApp.mock
      .onGet(/application\/10\/integrations/)
      .reply(200, [
        server({ tools: [tool('search')] }),
        server({ id: 6, name: 'Tracker', tools: [tool('issue')] }),
      ])
    testApp.mock.onPost('/integrations/mcp/5/refresh-tools/').reply(
      () =>
        new Promise((resolve) => {
          answer = () =>
            resolve([200, server({ tools: [tool('search'), tool('fetch')] })])
        })
    )
    const wrapper = await mountSection()
    await flushPromises()
    await openTools(wrapper, 0)
    buttonInBody('agent.connectedAppRefresh').click()
    await flushPromises()
    buttonInBody('action.cancel').click()
    // The modal finishes hiding on the next tick.
    await new Promise((resolve) => setTimeout(resolve))
    await openTools(wrapper, 1)
    answer()
    await flushPromises()

    expect(
      inBody('.modal__box .agent-tool-permissions__tool-name').map((name) =>
        name.textContent.trim()
      )
    ).toEqual(['issue'])
  })

  test('the review shows the parameters a tool is called with', async () => {
    const search = tool('search', {
      input_schema: {
        type: 'object',
        properties: {
          query: { type: 'string', description: 'What to look for' },
          limit: { type: 'integer' },
        },
        required: ['query'],
      },
    })
    testApp.mock
      .onGet(/application\/10\/integrations/)
      .reply(200, [server({ tools: [search] })])
    const wrapper = await mountSection()
    await flushPromises()

    await openTools(wrapper)

    // The description shows without opening anything.
    expect(buttonInBody('agent.toolDescription')).toBeUndefined()
    expect(
      inBody('.modal__box .agent-mcp-tools__description')[0].textContent
    ).toContain('search description')
    expect(inBody('.modal__box .agent-mcp-tools__parameter')).toHaveLength(0)
    buttonInBody('agent.connectedAppToolParameters').click()
    await flushPromises()

    const parameters = inBody('.modal__box .agent-mcp-tools__parameter').map(
      (parameter) =>
        [...parameter.children].map((part) => part.textContent.trim())
    )
    expect(parameters).toEqual([
      [
        'query',
        'string',
        'agent.connectedAppToolParameterRequired',
        'What to look for',
      ],
      ['limit', 'integer'],
    ])
  })

  test('the review shows the full input schema, with what the summary leaves out', async () => {
    const update = tool('update', {
      input_schema: {
        type: 'object',
        properties: { status: { type: 'string', enum: ['open', 'closed'] } },
      },
    })
    testApp.mock
      .onGet(/application\/10\/integrations/)
      .reply(200, [server({ tools: [update] })])
    const wrapper = await mountSection()
    await flushPromises()

    await openTools(wrapper)
    // The full schema sits inside the parameters.
    expect(buttonInBody('agent.connectedAppToolSchema')).toBeUndefined()
    buttonInBody('agent.connectedAppToolParameters').click()
    await flushPromises()
    buttonInBody('agent.connectedAppToolSchema').click()
    await flushPromises()

    const schema = inBody('.modal__box .agent-mcp-tools__schema')
    expect(JSON.parse(schema[0].textContent)).toEqual(update.input_schema)
  })

  test('a schema without top-level parameters can still be opened', async () => {
    const raw = tool('raw', {
      input_schema: { type: 'object', additionalProperties: true },
    })
    testApp.mock
      .onGet(/application\/10\/integrations/)
      .reply(200, [server({ tools: [raw] })])
    const wrapper = await mountSection()
    await flushPromises()

    await openTools(wrapper)
    expect(buttonInBody('agent.connectedAppToolParameters')).toBeUndefined()
    buttonInBody('agent.connectedAppToolSchema').click()
    await flushPromises()

    expect(
      JSON.parse(inBody('.modal__box .agent-mcp-tools__schema')[0].textContent)
    ).toEqual(raw.input_schema)
  })

  test('the footer counts the tools that are on', async () => {
    testApp.mock.onGet(/application\/10\/integrations/).reply(200, [
      server({
        tools: [
          tool('search', { enabled: true }),
          tool('delete'),
          tool('gone', { removed: true }),
        ],
      }),
    ])
    const wrapper = await mountSection()
    await flushPromises()

    await openTools(wrapper)
    const count = () =>
      [
        ...document.body.querySelectorAll(
          '.modal__box .agent-mcp-tools__count strong'
        ),
      ]
        .map((part) => part.textContent)
        .join(' / ')
    // A removed tool can't be turned on, so it isn't counted.
    expect(count()).toBe('1 / 2')
    inBody('.agent-mcp-tools__tool')[1].querySelector('.checkbox').click()
    await flushPromises()
    expect(count()).toBe('2 / 2')
  })

  test("another editor's change shows without a reload", async () => {
    const agent = await testApp.store.dispatch('application/forceCreate', {
      id: 10,
      type: 'agent',
      name: 'Helper',
      workspace: { id: 1 },
    })
    testApp.mock.onGet(/application\/10\/integrations/).reply(200, [server()])
    const wrapper = await testApp.mount(AgentConnectedAppsSection, {
      props: { editable: true },
      global: {
        provide: {
          agentApplication: ref(testApp.store.getters['application/get'](10)),
        },
      },
    })
    await flushPromises()
    const handlers = {}
    registerRealtimeEvents({
      registerEvent: (name, handler) => (handlers[name] = handler),
    })

    handlers.integration_updated(
      { store: testApp.store },
      { integration: server({ name: 'Renamed', application_id: 10 }) }
    )
    await flushPromises()

    expect(agent).toBeDefined()
    expect(wrapper.find('.agent-mcp-server-card__name').text()).toBe('Renamed')
  })

  const mountWithStore = async (servers) => {
    await testApp.store.dispatch('application/forceCreate', {
      id: 10,
      type: 'agent',
      name: 'Helper',
      workspace: { id: 1 },
    })
    testApp.mock.onGet(/application\/10\/integrations/).reply(200, servers)
    const wrapper = await testApp.mount(AgentConnectedAppsSection, {
      props: { editable: true },
      global: {
        provide: {
          agentApplication: ref(testApp.store.getters['application/get'](10)),
        },
      },
    })
    await flushPromises()
    const handlers = {}
    registerRealtimeEvents({
      registerEvent: (name, handler) => (handlers[name] = handler),
    })
    return { wrapper, handlers }
  }

  test("a tool another editor's refresh changed is saved as stored, not as picked before", async () => {
    const { wrapper, handlers } = await mountWithStore([
      server({ tools: [tool('search')] }),
    ])
    testApp.mock.onPatch('/integrations/mcp/5/tools/').reply(200, server())
    await openTools(wrapper)
    inBody('.agent-mcp-tools__columns')[1].querySelector('.checkbox').click()
    await flushPromises()

    handlers.integration_updated(
      { store: testApp.store },
      {
        integration: server({
          application_id: 10,
          tools: [
            tool('search', {
              definition_hash: 'search-hash-2',
              changed_since_review: true,
            }),
          ],
        }),
      }
    )
    await flushPromises()
    buttonInBody('action.save').click()
    await flushPromises()

    expect(body(testApp.mock.history.patch[0])).toEqual({
      tools: [
        {
          name: 'search',
          definition_hash: 'search-hash-2',
          enabled: false,
          ask_first: true,
        },
      ],
    })
  })

  test('a refresh that adds a tool lists it to pick', async () => {
    const { wrapper } = await mountWithStore([
      server({ tools: [tool('search')] }),
    ])
    testApp.mock
      .onPost('/integrations/mcp/5/refresh-tools/')
      .reply(200, server({ tools: [tool('search'), tool('fetch')] }))
    await openTools(wrapper)

    buttonInBody('agent.connectedAppRefresh').click()
    await flushPromises()

    const rows = inBody('.agent-mcp-tools__tool')
    expect(rows).toHaveLength(2)
    expect(rows[1].querySelectorAll('.checkbox')).toHaveLength(2)
  })

  test('viewers see the apps but cannot add or edit them', async () => {
    testApp.mock.onGet(/application\/10\/integrations/).reply(200, [server()])
    const wrapper = await mountSection(false)
    await flushPromises()

    expect(wrapper.find('.agent-connected-apps__add').exists()).toBe(false)
    expect(wrapper.find('.switch').exists()).toBe(false)
    expect(wrapper.find('.agent-action-card__footer').exists()).toBe(false)
    await expand(wrapper)
    expect(inputIn(card(wrapper), 'agent.connectedAppUrl').disabled).toBe(true)
    type(inputIn(card(wrapper), 'agent.connectedAppName'), 'Changed')
    await flushPromises()
    expect(card(wrapper).querySelector('.agent-mcp-server-card__actions')).toBe(
      null
    )
    await openTools(wrapper)
    expect(inBody('.modal__box .agent-tool-permissions__tool')).toHaveLength(0)
    expect(inBody('.modal__box').length).toBeGreaterThan(0)
  })

  test('connect an app adds an expanded draft card without a request', async () => {
    testApp.mock.onGet(/application\/10\/integrations/).reply(200, [server()])
    const wrapper = await mountSection()
    await flushPromises()

    const draft = await addApp(wrapper)

    expect(cards(wrapper)).toHaveLength(2)
    expect(draft.textContent).toContain('agent.connectedAppNew')
    expect(
      draft.querySelector('.agent-mcp-server-card__body').style.display
    ).toBe('')
    // A draft has nothing to switch and no tools yet.
    expect(draft.querySelector('.switch')).toBe(null)
    expect(draft.querySelector('.agent-mcp-server-card__tools')).toBe(null)
    expect(testApp.mock.history.post).toHaveLength(0)
  })

  test('removing a draft sends nothing', async () => {
    testApp.mock.onGet(/application\/10\/integrations/).reply(200, [])
    const wrapper = await mountSection()
    await flushPromises()

    const draft = await addApp(wrapper)
    type(inputIn(draft, 'agent.connectedAppName'), 'Docs')
    buttonIn(draft, 'agent.connectedAppRemove').click()
    await flushPromises()

    expect(cards(wrapper)).toHaveLength(0)
    expect(testApp.mock.history.post).toHaveLength(0)
    expect(testApp.mock.history.delete).toHaveLength(0)
  })

  test('the footer appears only after a change, and Cancel restores the values', async () => {
    testApp.mock.onGet(/application\/10\/integrations/).reply(200, [server()])
    const wrapper = await mountSection()
    await flushPromises()
    await expand(wrapper)
    const actions = () =>
      card(wrapper).querySelector('.agent-mcp-server-card__actions')

    expect(actions()).toBe(null)
    type(inputIn(card(wrapper), 'agent.connectedAppName'), 'Renamed')
    await flushPromises()
    expect(actions()).not.toBe(null)

    buttonIn(actions(), 'action.cancel').click()
    await flushPromises()

    expect(inputIn(card(wrapper), 'agent.connectedAppName').value).toBe('Docs')
    expect(actions()).toBe(null)
    expect(testApp.mock.history.patch).toHaveLength(0)
  })

  test('collapsing keeps unsaved edits', async () => {
    testApp.mock.onGet(/application\/10\/integrations/).reply(200, [server()])
    const wrapper = await mountSection()
    await flushPromises()

    await expand(wrapper)
    type(
      inputIn(card(wrapper), 'agent.connectedAppUrl'),
      'https://other.example.com/mcp'
    )
    await flushPromises()
    await wrapper.get('.agent-card-list-header__toggle-all').trigger('click')
    await flushPromises()
    expect(
      card(wrapper).querySelector('.agent-mcp-server-card__body').style.display
    ).toBe('none')
    await expand(wrapper)
    buttonIn(card(wrapper), 'action.save').click()
    await flushPromises()

    expect(inputIn(card(wrapper), 'agent.connectedAppUrl').value).toBe(
      'https://other.example.com/mcp'
    )
    expect(card(wrapper).textContent).toContain(
      'agent.connectedAppHeaderValueRequired'
    )
    expect(testApp.mock.history.patch).toHaveLength(0)
  })

  test('the switch saves only enabled', async () => {
    testApp.mock
      .onGet(/application\/10\/integrations/)
      .reply(200, [server({ enabled: true })])
    testApp.mock
      .onPatch('integration/5/')
      .reply(200, server({ enabled: false }))
    const wrapper = await mountSection()
    await flushPromises()

    await expand(wrapper)
    type(inputIn(card(wrapper), 'agent.connectedAppName'), 'Renamed')
    await flushPromises()
    card(wrapper).querySelector('.switch').click()
    await flushPromises()

    expect(body(testApp.mock.history.patch[0])).toEqual({ enabled: false })
    expect(card(wrapper).querySelector('.switch').classList).not.toContain(
      'switch--active'
    )
    // The pending edit is still there to save or cancel.
    expect(inputIn(card(wrapper), 'agent.connectedAppName').value).toBe(
      'Renamed'
    )
    expect(
      card(wrapper).querySelector('.agent-mcp-server-card__actions')
    ).not.toBe(null)
  })

  test('collapse all collapses every card', async () => {
    testApp.mock
      .onGet(/application\/10\/integrations/)
      .reply(200, [server(), server({ id: 6, name: 'Tracker' })])
    const wrapper = await mountSection()
    await flushPromises()
    const shown = () =>
      cards(wrapper).map(
        (item) =>
          item.element.querySelector('.agent-mcp-server-card__body').style
            .display !== 'none'
      )

    expect(shown()).toEqual([false, false])
    await wrapper.get('.agent-card-list-header__toggle-all').trigger('click')
    await flushPromises()
    expect(shown()).toEqual([true, true])
    await wrapper.get('.agent-card-list-header__toggle-all').trigger('click')
    await flushPromises()
    expect(shown()).toEqual([false, false])
  })

  test('a failed remove brings the app back and explains it', async () => {
    testApp.mock.onGet(/application\/10\/integrations/).reply(200, [server()])
    testApp.mock.onDelete('integration/5/').reply(500)
    const wrapper = await mountSection()
    await flushPromises()

    await expand(wrapper)
    buttonIn(card(wrapper), 'agent.connectedAppRemove').click()
    await flushPromises()
    buttonIn(card(wrapper), 'agent.connectedAppRemoveConfirm').click()
    await flushPromises()

    expect(cards(wrapper)).toHaveLength(1)
    expect(testApp.store.state.toast.items).toHaveLength(1)
  })

  test('the switch ignores clicks while it saves', async () => {
    testApp.mock
      .onGet(/application\/10\/integrations/)
      .reply(200, [server({ enabled: true })])
    const saving = deferredReply()
    testApp.mock.onPatch('integration/5/').reply(saving.reply)
    const wrapper = await mountSection()
    await flushPromises()

    card(wrapper).querySelector('.switch').click()
    await flushPromises()
    card(wrapper).querySelector('.switch').click()
    await flushPromises()
    saving.resolve(200, server({ enabled: false }))
    await flushPromises()

    expect(testApp.mock.history.patch).toHaveLength(1)
  })

  test('a long tool description can be read in full', async () => {
    const long = 'Lists issues. '.repeat(30).trim()
    testApp.mock
      .onGet(/application\/10\/integrations/)
      .reply(200, [server({ tools: [tool('search', { description: long })] })])
    const wrapper = await mountSection()
    await flushPromises()

    await openTools(wrapper)
    const description = () =>
      inBody('.modal__box .agent-mcp-tools__description')[0]
    expect(description().classList).toContain(
      'agent-mcp-tools__description--clamped'
    )
    buttonInBody('agent.connectedAppToolShowMore').click()
    await flushPromises()

    expect(description().classList).not.toContain(
      'agent-mcp-tools__description--clamped'
    )
    expect(description().textContent.trim()).toBe(long)
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
      const draft = await addApp(wrapper)
      type(inputIn(draft, 'agent.connectedAppName'), 'Linear')
      type(
        inputIn(draft, 'agent.connectedAppUrl'),
        'https://mcp.example.com/mcp'
      )
      buttonIn(draft, 'agent.connectedAppSignIn').click()
      await flushPromises()
    }

    // What the callback page reports once the provider redirected back.
    const report = (result) => {
      const channel = new BroadcastChannel(MCP_OAUTH_MESSAGE_TYPE)
      channel.postMessage({ type: MCP_OAUTH_MESSAGE_TYPE, ...result })
      channel.close()
    }

    const mockSignIn = () => {
      testApp.mock.onGet(/application\/10\/integrations/).reply(200, [])
      testApp.mock
        .onPost(/application\/10\/integrations/)
        .reply(200, oauthServer())
      testApp.mock.onPost('/integrations/mcp/5/oauth/start/').reply(200, {
        authorization_url: 'https://auth.example.com/authorize?state=abc',
      })
      testApp.mock
        .onPost('/integrations/mcp/5/refresh-tools/')
        .reply(
          200,
          oauthServer({ oauth_connected: true, tools: [tool('search')] })
        )
    }

    test('connecting opens the provider in a popup, then lists the tools', async () => {
      mockSignIn()
      const wrapper = await mountSection()
      await flushPromises()

      await createWithOAuth(wrapper)

      // The popup opens on the click itself, before any request.
      expect(window.open).toHaveBeenCalledTimes(1)
      expect(body(testApp.mock.history.post[0])).toMatchObject({
        auth_type: 'oauth',
        oauth_client_id: '',
      })
      expect(popup.location.href).toBe(
        'https://auth.example.com/authorize?state=abc'
      )

      // A provider page can cut the popup off from Baserow, which then sees it
      // as closed while the editor is still signing in.
      popup.closed = true
      await flushPromises()
      expect(inBody('.modal__box .agent-tool-permissions__tool')).toHaveLength(
        0
      )

      // The provider redirects back and the callback page reports.
      report({
        state: 'abc',
        integration: oauthServer({ oauth_connected: true }),
      })
      await vi.waitFor(() =>
        expect(
          inBody('.modal__box .agent-tool-permissions__tool')
        ).toHaveLength(1)
      )
      expect(testApp.mock.history.post.at(-1).url).toBe(
        '/integrations/mcp/5/refresh-tools/'
      )
    })

    test('another sign-in finishing leaves this one waiting', async () => {
      mockSignIn()
      const wrapper = await mountSection()
      await flushPromises()

      await createWithOAuth(wrapper)
      report({ state: 'other', integration: oauthServer() })
      await flushPromises()

      expect(popup.close).not.toHaveBeenCalled()
      expect(testApp.mock.history.post.at(-1).url).toBe(
        '/integrations/mcp/5/oauth/start/'
      )
    })

    test('a failed sign-in explains it and keeps the server', async () => {
      mockSignIn()
      const wrapper = await mountSection()
      await flushPromises()

      await createWithOAuth(wrapper)
      report({ state: 'abc', error: 'The sign-in was cancelled or refused.' })

      await vi.waitFor(() =>
        expect(card(wrapper).querySelector('.alert')?.textContent).toContain(
          'The sign-in was cancelled or refused.'
        )
      )
      // The saved server keeps its card, so signing in again edits it.
      expect(cards(wrapper)).toHaveLength(1)
      expect(card(wrapper).querySelector('.switch')).not.toBe(null)
    })

    test('a new URL replaces a client Baserow registered without asking for its secret', async () => {
      const registered = server({
        auth_type: 'oauth',
        oauth_connected: true,
        oauth_client_source: 'dynamic',
        has_auth_header_value: false,
        has_oauth_client_secret: true,
      })
      testApp.mock
        .onGet(/application\/10\/integrations/)
        .reply(200, [registered])
      testApp.mock
        .onPatch('integration/5/')
        .reply(200, { ...registered, oauth_connected: false })
      testApp.mock
        .onPost('/integrations/mcp/5/oauth/start/')
        .reply(200, { authorization_url: 'https://auth.example.com/authorize' })
      const wrapper = await mountSection()
      await flushPromises()

      await wrapper
        .find('.agent-mcp-server-card .agent-action-card__toggle')
        .trigger('click')
      await flushPromises()
      type(
        inputIn(card(wrapper), 'agent.connectedAppUrl'),
        'https://other.example.com/mcp'
      )
      await flushPromises()
      card(wrapper)
        .querySelector('.agent-mcp-server-card__actions button:last-child')
        .click()
      await flushPromises()

      expect(body(testApp.mock.history.patch[0])).toEqual({
        url: 'https://other.example.com/mcp',
      })
    })

    test('a blocked popup is explained', async () => {
      window.open.mockReturnValue(null)
      testApp.mock.onGet(/application\/10\/integrations/).reply(200, [])
      testApp.mock
        .onPost(/application\/10\/integrations/)
        .reply(200, oauthServer())
      const wrapper = await mountSection()
      await flushPromises()

      await createWithOAuth(wrapper)
      await flushPromises()

      expect(card(wrapper).querySelector('.alert')?.textContent).toContain(
        'agent.connectedAppPopupBlocked'
      )
      expect(testApp.mock.history.post.map(({ url }) => url)).not.toContain(
        '/integrations/mcp/5/refresh-tools/'
      )
    })

    test('clearing your own client id needs no secret', async () => {
      const own = oauthServer({
        oauth_connected: true,
        oauth_client_source: 'manual',
        oauth_client_id: 'my-client',
        has_oauth_client_secret: true,
      })
      testApp.mock.onGet(/application\/10\/integrations/).reply(200, [own])
      testApp.mock
        .onPatch('integration/5/')
        .reply(200, { ...own, oauth_connected: false })
      testApp.mock
        .onPost('/integrations/mcp/5/oauth/start/')
        .reply(200, { authorization_url: 'https://auth.example.com/authorize' })
      const wrapper = await mountSection()
      await flushPromises()

      await wrapper
        .find('.agent-mcp-server-card .agent-action-card__toggle')
        .trigger('click')
      await flushPromises()
      type(inputIn(card(wrapper), 'agent.connectedAppClientId'), '')
      await flushPromises()
      buttonIn(card(wrapper), 'agent.connectedAppSignIn').click()
      await flushPromises()

      expect(body(testApp.mock.history.patch[0])).toEqual({
        oauth_client_id: '',
      })
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
      expect(card(wrapper).querySelector('.alert').textContent).toContain(
        "doesn't support OAuth sign-in"
      )
    })

    test('a sign-in left waiting can be cancelled from the card', async () => {
      testApp.mock
        .onGet(/application\/10\/integrations/)
        .reply(200, [oauthServer({ tools: [tool('search')] })])
      testApp.mock.onPost('/integrations/mcp/5/oauth/start/').reply(200, {
        authorization_url: 'https://auth.example.com/authorize?state=abc',
      })
      const wrapper = await mountSection()
      await flushPromises()
      await expand(wrapper)

      card(wrapper)
        .querySelector('.agent-mcp-server-card__account button')
        .click()
      await flushPromises()
      // The editor closed the provider's popup without signing in.
      const cancel = buttonIn(
        card(wrapper).querySelector('.agent-mcp-server-card__actions'),
        'action.cancel'
      )
      expect(cancel.disabled).toBe(false)
      cancel.click()
      await flushPromises()

      expect(popup.close).toHaveBeenCalled()
      expect(
        card(wrapper).querySelector('.agent-mcp-server-card__actions')
      ).toBe(null)
      expect(
        card(wrapper).querySelector(
          '.agent-mcp-server-card__account .button-text__spinner'
        )
      ).toBe(null)
      // A sign-in finishing later no longer lists tools here.
      report({
        state: 'abc',
        integration: oauthServer({ oauth_connected: true }),
      })
      await flushPromises()
      await new Promise((resolve) => setTimeout(resolve, 50))
      await flushPromises()
      expect(testApp.mock.history.post.map(({ url }) => url)).not.toContain(
        '/integrations/mcp/5/refresh-tools/'
      )
      expect(inBody('.modal__box .agent-tool-permissions__tool')).toHaveLength(
        0
      )
    })

    test('a server without an account asks to sign in instead of listing tools', async () => {
      testApp.mock
        .onGet(/application\/10\/integrations/)
        .reply(200, [oauthServer({ tools: [tool('search')] })])
      const wrapper = await mountSection()
      await flushPromises()

      const server = wrapper.get('.agent-mcp-server-card')
      expect(server.text()).toContain('agent.connectedAppNotConnected')
      expect(server.text()).toContain('agent.connectedAppSignIn')
      expect(server.find('.agent-mcp-server-card__tools').exists()).toBe(false)
    })
  })
})
