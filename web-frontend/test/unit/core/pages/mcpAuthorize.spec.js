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

  const route = '/mcp/authorize?client_id=abc&scope=a&scope=b'

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
    const query = 'client_id=abc&scope=a&scope=b'
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
    const query = 'client_id=abc&scope=a&scope=b'
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
})
