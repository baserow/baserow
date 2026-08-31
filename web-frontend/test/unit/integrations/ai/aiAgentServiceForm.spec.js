import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'

import AIAgentServiceForm from '@baserow/modules/integrations/ai/components/services/AIAgentServiceForm'

const FormGroupStub = defineComponent({
  name: 'FormGroup',
  template: '<div><slot /><slot name="helper" /><slot name="error" /></div>',
})
const DropdownStub = defineComponent({
  name: 'Dropdown',
  props: { modelValue: { type: [String, Number], default: null } },
  template: '<div><slot /></div>',
})
const DropdownItemStub = defineComponent({
  name: 'DropdownItem',
  props: {
    name: { type: String, required: true },
    value: { type: String, required: true },
  },
  template: '<div />',
})
const PassthroughStub = defineComponent({ template: '<div />' })

const openAIModelType = { getName: () => 'OpenAI', getMaxTemperature: () => 2 }
const anthropicModelType = {
  getName: () => 'Anthropic',
  getMaxTemperature: () => 1,
}
const modelTypes = { openai: openAIModelType, anthropic: anthropicModelType }

const workspace = {
  id: 1,
  generative_ai_models_enabled: { openai: ['legacy-model'] },
  ai_features: { ai_agent: { models: { openai: ['db-model'] } } },
}

async function mountForm({ featureFlagEnabled, integration, defaultValues }) {
  return await mountSuspended(AIAgentServiceForm, {
    props: {
      application: { id: 1, workspace: { id: 1 } },
      defaultValues,
    },
    global: {
      stubs: {
        FormGroup: FormGroupStub,
        Dropdown: DropdownStub,
        DropdownItem: DropdownItemStub,
        IntegrationDropdown: PassthroughStub,
        InjectedFormulaInput: PassthroughStub,
        RadioGroup: PassthroughStub,
        FormInput: PassthroughStub,
        Button: PassthroughStub,
      },
      mocks: {
        $t: (key) => key,
        $featureFlagIsEnabled: () => featureFlagEnabled,
        $store: {
          getters: {
            'integration/getIntegrations': () => [integration],
            'integration/getIntegrationById': () => integration,
            'workspace/get': () => workspace,
          },
        },
        $registry: {
          getAll: () => modelTypes,
          get: (namespace, type) =>
            namespace === 'generativeAIModel' ? modelTypes[type] : {},
        },
      },
    },
  })
}

describe('AIAgentServiceForm', () => {
  test('lists ai_agent feature models when the flag is enabled', async () => {
    const wrapper = await mountForm({
      featureFlagEnabled: true,
      integration: { id: 5, type: 'ai', ai_settings: {} },
      defaultValues: { integration_id: 5, ai_generative_ai_type: 'openai' },
    })
    await flushPromises()

    expect(wrapper.vm.availableModels).toEqual(['db-model'])
  })

  test('lists legacy workspace models when the flag is disabled', async () => {
    const wrapper = await mountForm({
      featureFlagEnabled: false,
      integration: { id: 5, type: 'ai', ai_settings: {} },
      defaultValues: { integration_id: 5, ai_generative_ai_type: 'openai' },
    })
    await flushPromises()

    expect(wrapper.vm.availableModels).toEqual(['legacy-model'])
  })

  test('integration settings override the workspace models', async () => {
    const wrapper = await mountForm({
      featureFlagEnabled: true,
      integration: {
        id: 5,
        type: 'ai',
        ai_settings: { openai: { models: ['blob-model'] } },
      },
      defaultValues: { integration_id: 5, ai_generative_ai_type: 'openai' },
    })
    await flushPromises()

    expect(wrapper.vm.availableModels).toEqual(['blob-model'])
  })

  test('keeps a stale persisted selection visible with the flag enabled', async () => {
    const wrapper = await mountForm({
      featureFlagEnabled: true,
      integration: { id: 5, type: 'ai', ai_settings: {} },
      defaultValues: {
        integration_id: 5,
        ai_generative_ai_type: 'anthropic',
        ai_generative_ai_model: 'gone-model',
      },
    })
    await flushPromises()

    expect(wrapper.vm.availableModels).toEqual(['gone-model'])
    expect(
      wrapper.vm.availableProviders.map((provider) => provider.type)
    ).toContain('anthropic')
  })

  test('re-validates the selection when switching integration with the flag enabled', async () => {
    // Mounted already "post-switch" to integration 6, with a model stale from integration 5.
    const wrapper = await mountForm({
      featureFlagEnabled: true,
      integration: {
        id: 6,
        type: 'ai',
        ai_settings: { openai: { models: ['gpt-3.5'] } },
      },
      defaultValues: {
        integration_id: 6,
        ai_generative_ai_type: 'openai',
        ai_generative_ai_model: 'gpt-4',
      },
    })
    await flushPromises()

    // Stale-append keeps 'gpt-4' in the display list; the watcher must ignore it.
    expect(wrapper.vm.availableModels).toEqual(['gpt-3.5', 'gpt-4'])

    AIAgentServiceForm.watch['values.integration_id'].call(wrapper.vm, 6, 5)

    expect(wrapper.vm.values.ai_generative_ai_model).toBe('gpt-3.5')
  })
})
