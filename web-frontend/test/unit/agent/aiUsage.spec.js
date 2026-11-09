import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import { BaserowPlugin } from '@baserow/modules/core/plugins'
import AgentMessage from '@baserow/modules/agent/components/AgentMessage'
import { nowKey } from '@baserow/modules/core/composables/useNow'

const AIUsage = defineComponent({
  props: { pluginData: { type: Object, required: true } },
  setup(props) {
    return () => h('span', { class: 'test-ai-usage' }, props.pluginData.cost)
  },
})

class AIUsagePlugin extends BaserowPlugin {
  static getType() {
    return 'test_ai_usage'
  }

  getAIUsageComponents() {
    return [AIUsage]
  }
}

describe('AgentMessage AI usage', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
    testApp.getRegistry().register('plugin', new AIUsagePlugin())
  })

  afterEach(async () => {
    testApp.getRegistry().unregister('plugin', 'test_ai_usage')
    await testApp.afterEach()
  })

  test('shows the AI usage of a reply in its footer', async () => {
    const wrapper = await testApp.mount(AgentMessage, {
      props: {
        message: {
          role: 'assistant',
          content: 'Answer',
          status: 'completed',
          created_on: '2026-11-03T10:00:00Z',
          plugin_data: { cost: '3 credits' },
        },
      },
      global: { provide: { [nowKey]: ref(Date.now()) } },
    })

    expect(wrapper.get('.chat-message__footer .test-ai-usage').text()).toBe(
      '3 credits'
    )
  })
})
