import flushPromises from 'flush-promises'
import { TestApp } from '@baserow/test/helpers/testApp'
import MCPAuthorize from '@baserow/modules/core/pages/mcpAuthorize.vue'

describe('MCP authorize page', () => {
  let testApp = null

  const consent = {
    client_id: 'abc',
    client_name: 'Claude',
    redirect_host: 'claude.ai',
    registration_source: 'cimd',
    workspaces: [
      { id: 1, name: 'W' },
      { id: 2, name: 'Other' },
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
    ],
  }
  const allTools = ['list_tables', 'create_rows', 'delete_rows']

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
    testApp.authenticate({ id: 1, preferences: {} })
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
    return { wrapper, assign }
  }

  function toolCheckbox(wrapper, name) {
    return wrapper.find(`[data-test="mcp-authorize-tool-${name}"] input`)
  }

  test('shows workspaces and tools grouped and ticked', async () => {
    const { wrapper } = await mountWithConsent()
    // The test i18n returns message keys, so only API values are visible.
    expect(wrapper.text()).toContain('W')
    const read = wrapper.find('[data-test="mcp-authorize-tools-read"]')
    const change = wrapper.find('[data-test="mcp-authorize-tools-change"]')
    expect(read.text()).toContain('List tables')
    expect(read.text()).not.toContain('Create rows')
    expect(change.text()).toContain('Create rows')
    expect(change.text()).toContain('Delete rows')
    expect(
      change.findAll('.mcp-authorize__tool-hint').map((hint) => hint.text())
    ).toEqual(['mcpAuthorize.destructiveHint'])
    for (const name of allTools) {
      expect(toolCheckbox(wrapper, name).element.checked).toBe(true)
    }
  })

  test('allow posts the workspace and every ticked tool', async () => {
    testApp.mock
      .onPost('/mcp/oauth/consent/', {
        query,
        allow: true,
        workspace_id: 1,
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
        workspace_id: 1,
        tools: ['list_tables', 'delete_rows'],
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
