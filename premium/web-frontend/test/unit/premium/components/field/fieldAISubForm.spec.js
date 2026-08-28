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

  const mountComponent = async (
    aiPrompt,
    {
      initialModels = workspace.generative_ai_models_enabled,
      refreshedModels = workspace.generative_ai_models_enabled,
      initialAIFeatures,
      refreshedAIFeatures,
      selectedModel = 'gpt-4',
    } = {}
  ) => {
    await testApp.getStore().dispatch('workspace/forceCreate', {
      ...workspace,
      generative_ai_models_enabled: initialModels,
      ...(initialAIFeatures === undefined
        ? {}
        : { ai_features: initialAIFeatures }),
    })
    testApp.mock.onGet('/workspaces/').reply(200, [
      {
        ...workspace,
        generative_ai_models_enabled: refreshedModels,
        ...(refreshedAIFeatures === undefined
          ? {}
          : { ai_features: refreshedAIFeatures }),
      },
    ])
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
          ai_generative_ai_model: selectedModel,
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

  test('a disabled model is removed before it can be selected', async () => {
    const wrapper = await mountComponent(
      {
        formula: "'hello'",
        mode: 'advanced',
      },
      {
        initialModels: { openai: ['gpt-4', 'disabled-model'] },
        refreshedModels: { openai: ['gpt-4'] },
        selectedModel: 'disabled-model',
      }
    )

    const optionNames = wrapper
      .findAll('.select__item-name-text')
      .map((item) => item.text())
    expect(optionNames).not.toContain('disabled-model')
    wrapper.vm.submit()
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('submitted')).toBeUndefined()
    expect(wrapper.find('.control__messages--error').exists()).toBe(true)
  })

  test('uses AI Fields eligibility without narrowing generic AI consumers', async () => {
    const aiFeatures = {
      ai_fields: {
        is_enabled: true,
        models: { openai: ['gpt-4'] },
      },
    }
    const wrapper = await mountComponent(
      { formula: "'hello'", mode: 'advanced' },
      {
        initialModels: { openai: ['gpt-4', 'kuma-only'] },
        refreshedModels: { openai: ['gpt-4', 'kuma-only'] },
        initialAIFeatures: aiFeatures,
        refreshedAIFeatures: aiFeatures,
      }
    )

    const optionNames = wrapper
      .findAll('.select__item-name-text')
      .map((item) => item.text())
    expect(optionNames).toContain('gpt-4')
    expect(optionNames).not.toContain('kuma-only')
  })
})
