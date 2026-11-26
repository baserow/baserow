import { defineComponent, h } from 'vue'
import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import { BaserowPlugin } from '@baserow/modules/core/plugins'
import GenerateAIValuesJobListItem from '@baserow_premium/components/field/GenerateAIValuesJobListItem'

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

describe('GenerateAIValuesJobListItem component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new PremiumTestApp()
    testApp.getRegistry().register('plugin', new AIUsagePlugin())
  })

  afterEach(async () => {
    testApp.getRegistry().unregister('plugin', 'test_ai_usage')
    await testApp.afterEach()
  })

  test('shows the AI usage of a finished job with its plugin data', async () => {
    const wrapper = await testApp.mount(GenerateAIValuesJobListItem, {
      props: {
        field: { id: 1 },
        jobItem: {
          id: 1,
          state: 'finished',
          row_ids: [1],
          plugin_data: { cost: '2 credits' },
        },
      },
    })

    expect(wrapper.get('.test-ai-usage').text()).toBe('2 credits')
  })

  test('tells why a job failed', async () => {
    const wrapper = await testApp.mount(GenerateAIValuesJobListItem, {
      props: {
        field: { id: 1 },
        jobItem: {
          id: 1,
          state: 'failed',
          row_ids: [1],
          human_readable_error: 'No AI credits left.',
        },
      },
    })

    expect(wrapper.get('.generate-ai-values-job__error').text()).toBe(
      'No AI credits left.'
    )
  })
})
