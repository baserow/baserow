import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import GenerateAIValuesContextItem from '@baserow_premium/components/field/GenerateAIValuesContextItem'

describe('GenerateAIValuesContextItem component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new PremiumTestApp()
    testApp.giveCurrentUserGlobalPremiumFeatures()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const workspace = {
    id: 1,
    name: 'testWorkspace',
    generative_ai_models_enabled: { openai: ['gpt-4'] },
  }

  const aiField = {
    id: 1,
    name: 'AI field',
    order: 0,
    type: 'ai',
    primary: false,
    ai_generative_ai_type: 'openai',
    ai_generative_ai_model: 'gpt-4',
    ai_output_type: 'text',
    error: null,
  }

  const mountComponent = (field) =>
    testApp.mount(GenerateAIValuesContextItem, {
      props: {
        field,
        table: { id: 1 },
        database: { id: 1, workspace },
      },
      global: {
        stubs: {
          GenerateAIValuesModal: true,
          PaidFeaturesModal: true,
        },
      },
    })

  test('item is disabled and does not open the modal when the prompt is broken', async () => {
    await testApp.getStore().dispatch('workspace/forceCreate', workspace)

    const wrapper = await mountComponent({ ...aiField, error: 'boom' })

    expect(wrapper.find('a').classes()).toContain('disabled')

    await wrapper.find('a').trigger('click')
    expect(wrapper.emitted('hide-context')).toBeUndefined()
  })

  test('item is enabled when the prompt is not broken', async () => {
    await testApp.getStore().dispatch('workspace/forceCreate', workspace)

    const wrapper = await mountComponent(aiField)

    expect(wrapper.find('a').classes()).not.toContain('disabled')
  })
})
