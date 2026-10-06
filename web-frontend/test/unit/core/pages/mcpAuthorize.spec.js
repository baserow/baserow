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
    endpoints: [{ id: 7, name: 'Main', workspace_id: 1, workspace_name: 'W' }],
  }

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
    testApp.mock.onGet('/workspaces/').reply(200, [{ id: 1, name: 'W' }])
  })

  afterEach(async () => {
    vi.unstubAllGlobals()
    await testApp.afterEach()
  })

  test('lists endpoints and posts the selection with the full query', async () => {
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query } })
      .reply(200, consent)
    testApp.mock
      .onPost('/mcp/oauth/consent/', { query, allow: true, endpoint_id: 7 })
      .reply(200, {
        redirect_url: 'https://claude.ai/api/mcp/auth_callback?code=x',
      })
    const assign = vi.fn()
    vi.stubGlobal('location', { assign })

    const wrapper = await testApp.mount(MCPAuthorize, { route })
    // The test i18n returns message keys, so only the endpoint label is visible.
    expect(wrapper.text()).toContain('Main (W)')
    await wrapper.find('[data-test="mcp-authorize-allow"]').trigger('click')
    await flushPromises()
    expect(assign).toHaveBeenCalledWith(
      'https://claude.ai/api/mcp/auth_callback?code=x'
    )
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
    expect(wrapper.text()).toContain('Main (W)')
  })

  test('an invalid request value sends an empty query', async () => {
    testApp.mock
      .onGet('/mcp/oauth/consent/', { params: { query: '' } })
      .reply(400, { error: 'invalid_request' })
    const wrapper = await testApp.mount(MCPAuthorize, {
      route: '/mcp-authorize?request=%25%25',
    })
    expect(wrapper.text()).not.toContain('Main (W)')
  })
})
