import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import FieldAISubForm from '@baserow_premium/components/field/FieldAISubForm'

describe('FieldAISubForm component', () => {
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

  const mountComponent = async (aiPrompt) => {
    await testApp.getStore().dispatch('workspace/forceCreate', workspace)
    const wrapper = await testApp.mount(FieldAISubForm, {
      props: {
        table: { id: 10 },
        view: {},
        allFieldsInTable: [],
        database: { id: 100, workspace: { id: workspace.id } },
        fieldType: 'ai',
        defaultValues: {
          name: 'AI field',
          type: 'ai',
          ai_generative_ai_type: 'openai',
          ai_generative_ai_model: 'gpt-4',
          ai_output_type: 'text',
          ai_prompt: aiPrompt,
        },
      },
    })
    await wrapper.vm.$nextTick()
    return wrapper
  }

  test('a stored invalid prompt shows an error and blocks the form', async () => {
    const wrapper = await mountComponent({
      formula: "get('fields.field_1') x hello",
      mode: 'advanced',
    })

    expect(wrapper.find('.control__messages--error').exists()).toBe(true)
    // The parent FieldForm consults this to decide whether it may submit.
    expect(wrapper.vm.isFormValid()).toBe(false)
  })

  test('a valid prompt shows no error and the form can submit', async () => {
    const wrapper = await mountComponent({
      formula: "'hello'",
      mode: 'advanced',
    })

    expect(wrapper.find('.control__messages--error').exists()).toBe(false)
    expect(wrapper.vm.isFormValid()).toBe(true)
  })
})
