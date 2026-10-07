import flushPromises from 'flush-promises'
import { TestApp } from '@baserow/test/helpers/testApp'
import McpOAuthConnections from '@baserow/modules/core/components/settings/McpOAuthConnections.vue'

describe('McpOAuthConnections', () => {
  let testApp = null

  const mcpUrl = 'https://api.example.com/mcp'
  const connections = [
    {
      id: 11,
      client_name: 'claude',
      verified: true,
      verified_host: 'claude.ai',
      workspace_id: 1,
      workspace_name: 'Sales',
      allowed_tools: ['list_tables', 'list_rows'],
      tool_count: 2,
      created: '2026-10-06T10:00:00Z',
    },
    {
      id: 12,
      client_name: 'Local client',
      verified: false,
      verified_host: null,
      workspace_id: 2,
      workspace_name: 'Ops',
      allowed_tools: null,
      tool_count: 20,
      created: '2026-10-05T10:00:00Z',
    },
  ]

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  async function mount(data) {
    testApp.mock.onGet('/mcp/oauth/connections/').reply(200, data)
    const wrapper = await testApp.mount(McpOAuthConnections)
    await flushPromises()
    return wrapper
  }

  test('renders nothing and reports disabled when OAuth is off', async () => {
    const wrapper = await mount({
      oauth_enabled: false,
      mcp_url: null,
      connections: [],
    })
    expect(wrapper.find('.mcp-oauth-connections').exists()).toBe(false)
    expect(wrapper.emitted('loaded')).toEqual([[false]])
  })

  test('shows the URL and the client tabs', async () => {
    const wrapper = await mount({
      oauth_enabled: true,
      mcp_url: mcpUrl,
      connections: [],
    })
    expect(wrapper.emitted('loaded')).toEqual([[true]])
    expect(wrapper.find('[data-test="mcp-oauth-url"]').text()).toBe(mcpUrl)
    const text = wrapper.text()
    for (const title of ['Claude', 'Claude Code', 'ChatGPT', 'Cursor']) {
      expect(text).toContain(title)
    }
    expect(wrapper.find('[data-test="mcp-oauth-empty"]').exists()).toBe(true)
  })

  test('lists connections with badge, workspace and tool count', async () => {
    const wrapper = await mount({
      oauth_enabled: true,
      mcp_url: mcpUrl,
      connections,
    })
    const first = wrapper.find('[data-test="mcp-oauth-connection-11"]')
    const second = wrapper.find('[data-test="mcp-oauth-connection-12"]')
    expect(first.find('.mcp-oauth-connections__avatar').text()).toBe('C')
    expect(first.text()).toContain('claude')
    expect(first.text()).toContain('Sales')
    // The test i18n returns message keys.
    expect(first.text()).toContain('mcpOAuthConnections.tools')
    expect(first.find('[data-test="mcp-oauth-verified"]').exists()).toBe(true)
    expect(second.text()).toContain('Ops')
    expect(second.find('[data-test="mcp-oauth-verified"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="mcp-oauth-empty"]').exists()).toBe(false)
  })

  test('disconnect asks once, then deletes and removes the row', async () => {
    const wrapper = await mount({
      oauth_enabled: true,
      mcp_url: mcpUrl,
      connections,
    })
    testApp.mock.onDelete('/mcp/oauth/connections/11/').reply(204)
    const row = () => wrapper.find('[data-test="mcp-oauth-connection-11"]')
    const button = () => row().find('[data-test="mcp-oauth-disconnect"]')

    await button().trigger('click')
    await flushPromises()
    expect(testApp.mock.history.delete.length).toBe(0)
    expect(button().text()).toBe('mcpOAuthConnections.confirmDisconnect')

    await button().trigger('click')
    await flushPromises()
    expect(testApp.mock.history.delete.map((r) => r.url)).toEqual([
      '/mcp/oauth/connections/11/',
    ])
    expect(row().exists()).toBe(false)
    expect(wrapper.find('[data-test="mcp-oauth-connection-12"]').exists()).toBe(
      true
    )
  })

  test('uses only its own block elements', async () => {
    const wrapper = await mount({
      oauth_enabled: true,
      mcp_url: mcpUrl,
      connections: [],
    })
    expect(wrapper.find('[class*="mcp-endpoint__"]').exists()).toBe(false)
    expect(wrapper.find('.mcp-oauth-connections__url-box').text()).toContain(
      '/mcp'
    )
  })
})
