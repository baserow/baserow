import flushPromises from 'flush-promises'
import { TestApp } from '@baserow/test/helpers/testApp'
import McpEndpointSettings from '@baserow/modules/core/components/settings/McpEndpointSettings.vue'

describe('McpEndpointSettings', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  async function mount(oauthEnabled) {
    testApp.mock.onGet('/mcp/oauth/connections/').reply(200, {
      oauth_enabled: oauthEnabled,
      mcp_url: oauthEnabled ? 'https://api.example.com/mcp' : null,
      connections: [],
    })
    testApp.mock.onGet('/mcp/endpoints/').reply(200, [])
    const wrapper = await testApp.mount(McpEndpointSettings)
    await flushPromises()
    return wrapper
  }

  const oauth = (wrapper) => wrapper.find('.mcp-oauth-connections')
  const endpoints = (wrapper) => wrapper.find('[data-test="mcp-endpoint-list"]')
  const configOnly = (wrapper) =>
    wrapper.find('[data-test="mcp-endpoint-config-only"]')
  const tabs = (wrapper) =>
    wrapper.findAll(
      '.mcp-endpoint-settings__tabs > .tabs__header > .tabs__item'
    )

  test('shows only the endpoints without tabs when OAuth is off', async () => {
    const wrapper = await mount(false)

    expect(wrapper.find('.mcp-endpoint-settings__tabs').exists()).toBe(false)
    expect(oauth(wrapper).exists()).toBe(false)
    expect(endpoints(wrapper).isVisible()).toBe(true)
    expect(configOnly(wrapper).exists()).toBe(false)
  })

  test('warns that endpoints only work in config files when OAuth is on', async () => {
    const wrapper = await mount(true)

    await tabs(wrapper)[1].trigger('click')

    expect(configOnly(wrapper).isVisible()).toBe(true)
    expect(configOnly(wrapper).text()).toContain(
      'mcpEndpointSettings.configOnlyMessage'
    )
  })

  test('switches between the OAuth and endpoint tabs', async () => {
    const wrapper = await mount(true)

    expect(tabs(wrapper).map((tab) => tab.text())).toEqual([
      'mcpEndpointSettings.oauthTab',
      'mcpEndpointSettings.endpointTab',
    ])
    expect(oauth(wrapper).isVisible()).toBe(true)
    expect(endpoints(wrapper).isVisible()).toBe(false)

    await tabs(wrapper)[1].trigger('click')

    expect(oauth(wrapper).isVisible()).toBe(false)
    expect(endpoints(wrapper).isVisible()).toBe(true)
  })
})
