import flushPromises from 'flush-promises'
import { TestApp } from '@baserow/test/helpers/testApp'
import MCPAuthorize from '@baserow/modules/core/pages/mcpAuthorize.vue'
import { authenticatedUnlessError } from '@baserow/modules/core/utils/mcpAuthorize'

describe('MCP authorize page', () => {
  let testApp = null

  const consent = {
    client_id: 'abc',
    client_name: 'claude Code',
    redirect_host: 'localhost',
    registration_source: 'cimd',
    verified: true,
    verified_host: 'claude.ai',
    workspaces: [
      { id: 1, name: 'W', database_count: 0 },
      { id: 2, name: 'Other', database_count: 3 },
    ],
    tools: [
      {
        name: 'list_tables',
        title: 'List tables',
        read_only: true,
        destructive: false,
        group: 'database_read',
      },
      {
        name: 'create_rows',
        title: 'Create rows',
        read_only: false,
        destructive: false,
        group: 'database_edit',
      },
      {
        name: 'delete_rows',
        title: 'Delete rows',
        read_only: false,
        destructive: true,
        group: 'database_delete',
      },
      {
        name: 'update_rows',
        title: 'Update rows',
        read_only: false,
        destructive: true,
        group: 'database_edit',
      },
    ],
    groups: [
      {
        type: 'database_read',
        title: 'Read databases',
        area: 'database',
        read_only_preset: true,
      },
      {
        type: 'database_edit',
        title: 'Edit databases',
        area: 'database',
        read_only_preset: false,
      },
      {
        type: 'database_delete',
        title: 'Delete in databases',
        area: 'database',
        read_only_preset: false,
      },
    ],
  }
  const allTools = ['list_tables', 'create_rows', 'delete_rows', 'update_rows']

  // A real authorize query: percent-encoded values and a PKCE challenge whose
  // base64url form contains `-` and `_`.
  const query =
    'response_type=code&client_id=abc' +
    '&redirect_uri=http%3A%2F%2F127.0.0.1%3A33418%2Fcallback' +
    '&code_challenge=x-_y%2B~&code_challenge_method=S256&scope=mcp&scope=b' +
    '&state=s%C3%A9&resource=http%3A%2F%2Flocalhost%3A8000%2Fmcp'
  const request = Buffer.from(query).toString('base64url')
  const route = `/mcp-authorize/${request}`

  beforeEach(() => {
    testApp = new TestApp()
    testApp.authenticate({
      id: 1,
      username: 'dev@baserow.io',
      preferences: {},
    })
    testApp.mock.onGet('/settings/').reply(200, {})
  })

  afterEach(async () => {
    vi.unstubAllGlobals()
    await testApp.afterEach()
  })

  // Nuxt's prefetch scheduler resolves each navigation against `location.href`.
  function stubLocation() {
    const assign = vi.fn()
    vi.stubGlobal('location', { href: window.location.href, assign })
    return assign
  }

  async function mountWithConsent() {
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query } })
      .reply(200, consent)
    const assign = stubLocation()
    const wrapper = await testApp.mount(MCPAuthorize, { route })
    await flushPromises()
    return { wrapper, assign }
  }

  // The test i18n drops message params; this `$t` keeps them in the text.
  const withParams = {
    global: {
      mocks: {
        $t: (key, params) =>
          params ? `${key} ${JSON.stringify(params)}` : key,
      },
    },
  }

  function toolCheckbox(wrapper, name) {
    return wrapper.find(`[data-test="mcp-tool-picker-tool-${name}"] input`)
  }

  test('shows workspaces and tools grouped, with only reading ticked', async () => {
    const { wrapper } = await mountWithConsent()
    // The test i18n returns message keys, so only API values are visible.
    expect(wrapper.text()).toContain('Other')
    const group = (type) =>
      wrapper.find(`[data-test="mcp-tool-picker-group-${type}"]`)
    expect(group('database_read').text()).toContain('List tables')
    expect(group('database_read').text()).not.toContain('Create rows')
    expect(group('database_edit').text()).toContain('Create rows')
    expect(group('database_delete').text()).toContain('Delete rows')
    // Changing data is opt-in on a first connection.
    for (const name of allTools) {
      expect(toolCheckbox(wrapper, name).element.checked).toBe(
        name === 'list_tables'
      )
    }
  })

  test('the checkboxes show what is ticked and ticking updates them', async () => {
    testApp.mock
      .onPost('/mcp/oauth/consent/', {
        query,
        allow: true,
        workspace_id: 2,
        tools: ['list_tables', 'create_rows'],
      })
      .reply(200, { redirect_url: 'https://claude.ai/cb?code=v' })
    const { wrapper, assign } = await mountWithConsent()
    const checkbox = (name) =>
      wrapper.find(`[data-test="mcp-tool-picker-tool-${name}"]`)
    expect(checkbox('list_tables').classes()).toContain('checkbox--checked')
    expect(checkbox('create_rows').classes()).not.toContain('checkbox--checked')
    await toolCheckbox(wrapper, 'create_rows').setValue(true)
    expect(checkbox('create_rows').classes()).toContain('checkbox--checked')
    expect(checkbox('delete_rows').classes()).not.toContain('checkbox--checked')
    await wrapper.find('[data-test="mcp-authorize-allow"]').trigger('click')
    await flushPromises()
    expect(assign).toHaveBeenCalledWith('https://claude.ai/cb?code=v')
  })

  test('the header shows the client initial, title and returns-to host', async () => {
    const { wrapper } = await mountWithConsent()
    expect(wrapper.find('[data-test="mcp-authorize-avatar"]').text()).toBe('C')
    expect(wrapper.find('[data-test="mcp-authorize-title"]').text()).toBe(
      'mcpAuthorize.titleFrom'
    )
    expect(wrapper.find('[data-test="mcp-authorize-returns"]').text()).toBe(
      'mcpAuthorize.returns'
    )
  })

  test('a verified client is titled with its name and the host that published it', async () => {
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query } })
      .reply(200, consent)
    stubLocation()
    const wrapper = await testApp.mount(MCPAuthorize, { route, ...withParams })
    await flushPromises()
    // Any host can publish a metadata document with any name, so the host
    // stays in the title next to the name.
    const title = wrapper.find('[data-test="mcp-authorize-title"]').text()
    expect(title).toContain('mcpAuthorize.titleFrom')
    expect(title).toContain('claude Code')
    expect(title).toContain('claude.ai')
    expect(
      wrapper.find('[data-test="mcp-authorize-unverified"]').exists()
    ).toBe(false)
  })

  test('an unverified client is named by its own name', async () => {
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query } })
      .reply(200, { ...consent, verified: false, verified_host: null })
    stubLocation()
    const wrapper = await testApp.mount(MCPAuthorize, { route, ...withParams })
    await flushPromises()

    const title = wrapper.find('[data-test="mcp-authorize-title"]').text()
    expect(title).toContain('mcpAuthorize.title {')
    expect(title).toContain('claude Code')
  })

  test('marks a self-registered client as not verified', async () => {
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query } })
      .reply(200, {
        ...consent,
        verified: false,
        verified_host: null,
        registration_source: 'dcr',
      })
    stubLocation()
    const wrapper = await testApp.mount(MCPAuthorize, { route, ...withParams })
    await flushPromises()

    expect(wrapper.find('[data-test="mcp-authorize-published"]').exists()).toBe(
      false
    )
    expect(
      wrapper.find('[data-test="mcp-authorize-unverified"]').text()
    ).toContain('localhost')
  })

  test('shows the signed in user and a database count per workspace', async () => {
    const { wrapper } = await mountWithConsent()
    expect(wrapper.find('[data-test="mcp-authorize-signed-in"]').exists()).toBe(
      true
    )
    // The test i18n returns message keys, so the count itself is not visible;
    // the description renders once per workspace item.
    const descriptions = wrapper.findAll('.select__item-description')
    expect(descriptions).toHaveLength(2)
  })

  test('refuses to show the consent form inside a frame', async () => {
    vi.stubGlobal('top', {})
    const { wrapper } = await mountWithConsent()
    expect(wrapper.find('[data-test="mcp-authorize-allow"]').exists()).toBe(
      false
    )
    expect(wrapper.find('[data-test="mcp-authorize-framed"]').text()).toBe(
      'mcpAuthorize.framed'
    )
    const consentCalls = [
      ...testApp.mock.history.get,
      ...testApp.mock.history.post,
    ].filter((request) => request.url.includes('/mcp/oauth/consent/'))
    expect(consentCalls).toHaveLength(0)
  })

  test('the read only preset ticks only the read tools', async () => {
    const { wrapper } = await mountWithConsent()
    await wrapper
      .find('[data-test="mcp-tool-picker-full-access"]')
      .trigger('click')
    await wrapper
      .find('[data-test="mcp-tool-picker-read-only"]')
      .trigger('click')
    const checked = allTools.filter(
      (name) => toolCheckbox(wrapper, name).element.checked
    )
    expect(checked).toEqual(['list_tables'])
  })

  test('none and full access toggle every tool', async () => {
    const { wrapper } = await mountWithConsent()
    await wrapper.find('[data-test="mcp-tool-picker-none"]').trigger('click')
    for (const name of allTools) {
      expect(toolCheckbox(wrapper, name).element.checked).toBe(false)
    }
    await wrapper
      .find('[data-test="mcp-tool-picker-full-access"]')
      .trigger('click')
    for (const name of allTools) {
      expect(toolCheckbox(wrapper, name).element.checked).toBe(true)
    }
  })

  test('defaults to the first workspace with databases', async () => {
    testApp.mock
      .onPost('/mcp/oauth/consent/', {
        query,
        allow: true,
        workspace_id: 1,
        tools: ['list_tables'],
      })
      .reply(200, { redirect_url: 'https://claude.ai/cb?code=z' })
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query } })
      .reply(200, {
        ...consent,
        workspaces: consent.workspaces.map((w) => ({
          ...w,
          database_count: 0,
        })),
      })
    const assign = stubLocation()
    const wrapper = await testApp.mount(MCPAuthorize, { route })
    await flushPromises()
    await wrapper.find('[data-test="mcp-authorize-allow"]').trigger('click')
    await flushPromises()
    expect(assign).toHaveBeenCalledWith('https://claude.ai/cb?code=z')
  })

  test('allow posts the workspace and every ticked tool', async () => {
    testApp.mock
      .onPost('/mcp/oauth/consent/', {
        query,
        allow: true,
        workspace_id: 2,
        tools: ['list_tables'],
      })
      .reply(200, {
        redirect_url: 'https://claude.ai/api/mcp/auth_callback?code=x',
      })
    const { wrapper, assign } = await mountWithConsent()
    await wrapper.find('[data-test="mcp-authorize-allow"]').trigger('click')
    await flushPromises()
    expect(assign).toHaveBeenCalledWith(
      'https://claude.ai/api/mcp/auth_callback?code=x'
    )
  })

  test('unticking a tool leaves it out of the request', async () => {
    testApp.mock
      .onPost('/mcp/oauth/consent/', {
        query,
        allow: true,
        workspace_id: 2,
        tools: ['list_tables', 'delete_rows', 'update_rows'],
      })
      .reply(200, { redirect_url: 'https://claude.ai/cb?code=y' })
    const { wrapper, assign } = await mountWithConsent()
    await wrapper
      .find('[data-test="mcp-tool-picker-full-access"]')
      .trigger('click')
    await toolCheckbox(wrapper, 'create_rows').setValue(false)
    await wrapper.find('[data-test="mcp-authorize-allow"]').trigger('click')
    await flushPromises()
    expect(assign).toHaveBeenCalledWith('https://claude.ai/cb?code=y')
  })

  test('allow is disabled when no tool is ticked', async () => {
    const { wrapper } = await mountWithConsent()
    const allow = wrapper.find('[data-test="mcp-authorize-allow"]')
    expect(allow.attributes('disabled')).toBeUndefined()
    for (const name of allTools) {
      await toolCheckbox(wrapper, name).setValue(false)
    }
    expect(allow.attributes('disabled')).toBeDefined()
  })

  test('ticks the tools of the existing grant for the workspace', async () => {
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query } })
      .reply(200, { ...consent, grants: { 2: ['list_tables'] } })
    stubLocation()
    const wrapper = await testApp.mount(MCPAuthorize, { route })
    await flushPromises()

    const checked = allTools.filter(
      (name) => toolCheckbox(wrapper, name).element.checked
    )
    expect(checked).toEqual(['list_tables'])
  })

  test('reconnecting preselects the granted workspace and its tools', async () => {
    // Workspace 2 has databases, but the client is connected to workspace 1.
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query } })
      .reply(200, { ...consent, grants: { 1: ['list_tables'] } })
    testApp.mock
      .onPost('/mcp/oauth/consent/', {
        query,
        allow: true,
        workspace_id: 1,
        tools: ['list_tables'],
      })
      .reply(200, { redirect_url: 'https://claude.ai/cb?code=g' })
    const assign = stubLocation()
    const wrapper = await testApp.mount(MCPAuthorize, { route })
    await flushPromises()

    await wrapper.find('[data-test="mcp-authorize-allow"]').trigger('click')
    await flushPromises()
    expect(assign).toHaveBeenCalledWith('https://claude.ai/cb?code=g')
  })

  test('warns when the client only redirects to loopback', async () => {
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query } })
      .reply(200, { ...consent, loopback_only: true })
    stubLocation()
    const wrapper = await testApp.mount(MCPAuthorize, { route })
    await flushPromises()

    expect(
      wrapper.find('[data-test="mcp-authorize-loopback-warning"]').exists()
    ).toBe(true)
  })

  test('explains when no workspace can be connected', async () => {
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query } })
      .reply(200, { ...consent, workspaces: [] })
    stubLocation()
    const wrapper = await testApp.mount(MCPAuthorize, { route })
    await flushPromises()

    expect(
      wrapper.find('[data-test="mcp-authorize-no-workspaces"]').exists()
    ).toBe(true)
    expect(
      wrapper.find('[data-test="mcp-authorize-allow"]').attributes('disabled')
    ).toBeDefined()
  })

  test('deny posts allow false', async () => {
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query } })
      .reply(200, consent)
    testApp.mock
      .onPost('/mcp/oauth/consent/', { query, allow: false })
      .reply(200, { redirect_url: 'https://claude.ai/cb?error=access_denied' })
    const assign = stubLocation()

    const wrapper = await testApp.mount(MCPAuthorize, { route })
    await wrapper.find('[data-test="mcp-authorize-deny"]').trigger('click')
    await flushPromises()
    expect(assign).toHaveBeenCalledWith(
      'https://claude.ai/cb?error=access_denied'
    )
  })

  test('the query survives the logged-out login round trip', async () => {
    // The `authenticated` middleware sends the user to
    // `/login?original=<encodeURI(fullPath)>` and login pushes `original`
    // back. The request value must reach the page unchanged even when
    // encoded once more along the way.
    expect(request).toMatch(/^[A-Za-z0-9_-]+$/)
    const original = encodeURI(route)
    const router = useRouter()
    const loginPath = router.resolve({
      path: '/login',
      query: { original },
    }).fullPath
    const back = router.resolve(loginPath).query.original
    for (const path of [back, encodeURI(back)]) {
      expect(path).toBe(route)
    }

    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query } })
      .reply(200, consent)
    const wrapper = await testApp.mount(MCPAuthorize, { route: back })
    await flushPromises()
    expect(wrapper.text()).toContain('List tables')
  })

  test('a rejected request shows the readable detail', async () => {
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query } })
      .reply(400, {
        error: 'invalid_request',
        detail: 'Mismatching redirect URI.',
      })
    const wrapper = await testApp.mount(MCPAuthorize, { route })
    await flushPromises()
    expect(wrapper.text()).toContain('Mismatching redirect URI.')
    expect(wrapper.text()).not.toContain('invalid_request')
  })

  test('a rejected request without detail shows the error code', async () => {
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query } })
      .reply(400, { error: 'invalid_request' })
    const wrapper = await testApp.mount(MCPAuthorize, { route })
    await flushPromises()
    expect(wrapper.text()).toContain('invalid_request')
  })

  test.each([
    ['a server error', (mock) => mock.reply(500)],
    ['a network error', (mock) => mock.networkError()],
  ])('%s asks to try again', async (_, reply) => {
    reply(testApp.mock.onGet('/mcp/oauth/consent/', { params: { query } }))
    const wrapper = await testApp.mount(MCPAuthorize, { route })
    await flushPromises()
    expect(wrapper.text()).toContain('mcpAuthorize.loadFailed')
    expect(wrapper.text()).toContain('mcpAuthorize.loadFailedMessage')
    expect(wrapper.text()).not.toContain('mcpAuthorize.invalid')
  })

  function consentRequests() {
    return testApp.mock.history.get.filter(
      (r) => r.url === '/mcp/oauth/consent/'
    )
  }

  test('a known error code shows its own message without a consent request', async () => {
    const wrapper = await testApp.mount(MCPAuthorize, {
      route: '/mcp-authorize?error=unknown_client',
    })
    await flushPromises()
    expect(wrapper.text()).toContain('mcpAuthorize.invalid')
    expect(wrapper.text()).toContain('mcpAuthorize.unknownClient')
    expect(wrapper.find('[data-test="mcp-authorize-loading"]').exists()).toBe(
      false
    )
    expect(consentRequests()).toEqual([])
  })

  test('a rejected CIMD client is told it cannot sign in', async () => {
    const wrapper = await testApp.mount(MCPAuthorize, {
      route: '/mcp-authorize?error=client_rejected',
    })
    await flushPromises()
    expect(wrapper.text()).toContain('mcpAuthorize.clientRejected')
    expect(wrapper.text()).not.toContain('mcpAuthorize.invalidMessage')
  })

  test('an unknown error code shows the generic message', async () => {
    const wrapper = await testApp.mount(MCPAuthorize, {
      route: '/mcp-authorize?error=made_up',
    })
    await flushPromises()
    expect(wrapper.text()).toContain('mcpAuthorize.invalid')
    expect(wrapper.text()).toContain('mcpAuthorize.invalidMessage')
    expect(wrapper.text()).not.toContain('made_up')
    expect(consentRequests()).toEqual([])
  })

  test('an error description in the URL is never shown', async () => {
    const wrapper = await testApp.mount(MCPAuthorize, {
      route:
        '/mcp-authorize?error=invalid_request&error_description=' +
        encodeURIComponent('Call +1 555 0100 for support'),
    })
    await flushPromises()
    expect(wrapper.text()).toContain('mcpAuthorize.invalidMessage')
    expect(wrapper.text()).not.toContain('555')
  })

  test('the error page needs no sign in, the consent form does', async () => {
    testApp.store.commit('auth/LOGOFF')
    expect(
      authenticatedUnlessError({
        query: { error: 'unknown_client' },
        fullPath: '/mcp-authorize?error=unknown_client',
      })
    ).toBeUndefined()
    // Awaited, so the login navigation and its settings middleware finish while
    // the request mock is still in place.
    await authenticatedUnlessError({
      query: {},
      params: { request },
      fullPath: route,
    })
    expect(useRouter().currentRoute.value.name).toBe('login')
  })

  test('still reads a request sent as a query parameter', async () => {
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query } })
      .reply(200, consent)
    const wrapper = await testApp.mount(MCPAuthorize, {
      route: `/mcp-authorize?request=${request}`,
    })
    await flushPromises()
    expect(wrapper.text()).toContain('List tables')
  })

  test('an invalid request value sends an empty query', async () => {
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query: '' } })
      .reply(400, { error: 'invalid_request' })
    await testApp.mount(MCPAuthorize, { route: '/mcp-authorize/%25%25' })
    await flushPromises()
    expect(consentRequests().map((call) => call.params)).toEqual([
      { query: '' },
    ])
  })
})
