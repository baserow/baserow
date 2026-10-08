import flushPromises from 'flush-promises'
import { TestApp } from '@baserow/test/helpers/testApp'
import MCPAuthorize from '@baserow/modules/core/pages/mcpAuthorize.vue'

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
      },
      {
        name: 'create_rows',
        title: 'Create rows',
        read_only: false,
        destructive: false,
      },
      {
        name: 'delete_rows',
        title: 'Delete rows',
        read_only: false,
        destructive: true,
      },
      {
        name: 'update_rows',
        title: 'Update rows',
        read_only: false,
        destructive: true,
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
  const route = `/mcp-authorize?request=${request}`

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

  async function mountWithConsent() {
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query } })
      .reply(200, consent)
    const assign = vi.fn()
    vi.stubGlobal('location', { assign })
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
    return wrapper.find(`[data-test="mcp-authorize-tool-${name}"] input`)
  }

  test('shows workspaces and tools grouped and ticked', async () => {
    const { wrapper } = await mountWithConsent()
    // The test i18n returns message keys, so only API values are visible.
    expect(wrapper.text()).toContain('Other')
    const read = wrapper.find('[data-test="mcp-authorize-tools-read"]')
    const change = wrapper.find('[data-test="mcp-authorize-tools-change"]')
    expect(read.text()).toContain('List tables')
    expect(read.text()).not.toContain('Create rows')
    expect(change.text()).toContain('Create rows')
    expect(change.text()).toContain('Delete rows')
    for (const name of allTools) {
      expect(toolCheckbox(wrapper, name).element.checked).toBe(true)
    }
  })

  test('every tool checkbox is visually checked and unticking updates it', async () => {
    testApp.mock
      .onPost('/mcp/oauth/consent/', {
        query,
        allow: true,
        workspace_id: 2,
        tools: ['list_tables', 'create_rows', 'update_rows'],
      })
      .reply(200, { redirect_url: 'https://claude.ai/cb?code=v' })
    const { wrapper, assign } = await mountWithConsent()
    const checkbox = (name) =>
      wrapper.find(`[data-test="mcp-authorize-tool-${name}"]`)
    for (const name of allTools) {
      expect(checkbox(name).classes()).toContain('checkbox--checked')
    }
    await toolCheckbox(wrapper, 'delete_rows').setValue(false)
    expect(checkbox('delete_rows').classes()).not.toContain('checkbox--checked')
    expect(checkbox('create_rows').classes()).toContain('checkbox--checked')
    await wrapper.find('[data-test="mcp-authorize-allow"]').trigger('click')
    await flushPromises()
    expect(assign).toHaveBeenCalledWith('https://claude.ai/cb?code=v')
  })

  test('the header shows the client initial, title and returns-to host', async () => {
    const { wrapper } = await mountWithConsent()
    expect(wrapper.find('[data-test="mcp-authorize-avatar"]').text()).toBe('C')
    expect(wrapper.find('[data-test="mcp-authorize-title"]').text()).toBe(
      'mcpAuthorize.title'
    )
    expect(wrapper.find('[data-test="mcp-authorize-returns"]').text()).toBe(
      'mcpAuthorize.returns'
    )
  })

  test('the verified badge is shown only for verified clients', async () => {
    const { wrapper } = await mountWithConsent()
    expect(wrapper.find('[data-test="mcp-authorize-verified"]').exists()).toBe(
      true
    )
    wrapper.unmount()

    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query } })
      .reply(200, { ...consent, verified: false, verified_host: null })
    const other = await testApp.mount(MCPAuthorize, { route })
    await flushPromises()
    expect(other.find('[data-test="mcp-authorize-title"]').exists()).toBe(true)
    expect(other.find('[data-test="mcp-authorize-verified"]').exists()).toBe(
      false
    )
  })

  test('a verified client is named by its host', async () => {
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query } })
      .reply(200, consent)
    vi.stubGlobal('location', { assign: vi.fn() })
    const wrapper = await testApp.mount(MCPAuthorize, { route, ...withParams })
    await flushPromises()
    const title = wrapper.find('[data-test="mcp-authorize-title"]').text()
    expect(title).toContain('claude.ai')
    expect(title).not.toContain('claude Code')
  })

  test('an unverified client is named by its own name', async () => {
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query } })
      .reply(200, { ...consent, verified: false, verified_host: null })
    vi.stubGlobal('location', { assign: vi.fn() })
    const wrapper = await testApp.mount(MCPAuthorize, { route, ...withParams })
    await flushPromises()

    expect(wrapper.find('[data-test="mcp-authorize-title"]').text()).toContain(
      'claude Code'
    )
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
    vi.stubGlobal('location', { assign: vi.fn() })
    const wrapper = await testApp.mount(MCPAuthorize, { route, ...withParams })
    await flushPromises()

    expect(wrapper.find('[data-test="mcp-authorize-verified"]').exists()).toBe(
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

  test('destructive tools get a Deletes or Overwrites badge', async () => {
    const { wrapper } = await mountWithConsent()
    const badge = (name) =>
      wrapper.find(`[data-test="mcp-authorize-badge-${name}"]`)
    expect(badge('delete_rows').text()).toBe('mcpAuthorize.deletes')
    expect(badge('delete_rows').classes()).toContain('badge--red')
    expect(badge('update_rows').text()).toBe('mcpAuthorize.overwrites')
    expect(badge('update_rows').classes()).toContain('badge--yellow')
    expect(badge('create_rows').exists()).toBe(false)
  })

  test('none and select all are keyboard reachable buttons', async () => {
    const { wrapper } = await mountWithConsent()
    for (const key of ['select-all', 'select-none']) {
      const button = wrapper.find(`[data-test="mcp-authorize-${key}"]`)
      expect(button.element.tagName).toBe('BUTTON')
      expect(button.attributes('type')).toBe('button')
    }
  })

  test('none and select all toggle every tool', async () => {
    const { wrapper } = await mountWithConsent()
    await wrapper
      .find('[data-test="mcp-authorize-select-none"]')
      .trigger('click')
    for (const name of allTools) {
      expect(toolCheckbox(wrapper, name).element.checked).toBe(false)
    }
    await wrapper
      .find('[data-test="mcp-authorize-select-all"]')
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
        tools: allTools,
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
    const assign = vi.fn()
    vi.stubGlobal('location', { assign })
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
        tools: allTools,
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
    vi.stubGlobal('location', { assign: vi.fn() })
    const wrapper = await testApp.mount(MCPAuthorize, { route })
    await flushPromises()

    const checked = allTools.filter(
      (name) => toolCheckbox(wrapper, name).element.checked
    )
    expect(checked).toEqual(['list_tables'])
  })

  test('keeps every tool ticked for a grant that allows all tools', async () => {
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query } })
      .reply(200, { ...consent, grants: { 2: null } })
    vi.stubGlobal('location', { assign: vi.fn() })
    const wrapper = await testApp.mount(MCPAuthorize, { route })
    await flushPromises()

    for (const name of allTools) {
      expect(toolCheckbox(wrapper, name).element.checked).toBe(true)
    }
  })

  test('warns when the client only redirects to loopback', async () => {
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query } })
      .reply(200, { ...consent, loopback_only: true })
    vi.stubGlobal('location', { assign: vi.fn() })
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
    vi.stubGlobal('location', { assign: vi.fn() })
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
    const assign = vi.fn()
    vi.stubGlobal('location', { assign })

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

  test('an invalid request value sends an empty query', async () => {
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query: '' } })
      .reply(400, { error: 'invalid_request' })
    const wrapper = await testApp.mount(MCPAuthorize, {
      route: '/mcp-authorize?request=%25%25',
    })
    expect(wrapper.text()).not.toContain('List tables')
  })
})
