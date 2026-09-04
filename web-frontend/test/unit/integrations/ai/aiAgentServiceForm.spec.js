import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'

import AIAgentServiceForm from '@baserow/modules/integrations/ai/components/services/AIAgentServiceForm'
import { AIAgentServiceType } from '@baserow/modules/integrations/ai/serviceTypes'

const FormGroupStub = defineComponent({
  name: 'FormGroup',
  props: {
    label: { type: String, default: null },
    error: { type: Boolean, default: false },
  },
  template:
    '<div class="form-group" :data-label="label" :data-error="error"><slot /><slot name="helper" /><slot name="error" /></div>',
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
    disabled: { type: Boolean, default: false },
  },
  template:
    '<div class="dropdown-item" :data-value="value" :aria-disabled="disabled">{{ name }}</div>',
})
const PassthroughStub = defineComponent({ template: '<div />' })

const openAIModelType = {
  getName: () => 'OpenAI',
  getMaxTemperature: () => 2,
  isIntegrationSettingsComplete: (settings) => Boolean(settings.api_key),
}
const anthropicModelType = {
  getName: () => 'Anthropic',
  getMaxTemperature: () => 1,
  isIntegrationSettingsComplete: (settings) => Boolean(settings.api_key),
}
const modelTypes = { openai: openAIModelType, anthropic: anthropicModelType }

const workspace = {
  id: 1,
  generative_ai_models_enabled: { openai: ['legacy-model'] },
  ai_features: { ai_agent: { models: { openai: ['db-model'] } } },
}

async function mountForm({
  featureFlagEnabled,
  integration,
  defaultValues,
  workspace: workspaceValue = workspace,
}) {
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
            'workspace/get': () => workspaceValue,
          },
        },
        $registry: {
          getAll: () => modelTypes,
          get: (namespace, type) => {
            if (namespace !== 'generativeAIModel') {
              return {}
            }
            if (!modelTypes[type]) {
              throw new Error(`Missing model type: ${type}`)
            }
            return modelTypes[type]
          },
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

  test('limits partial integration settings to legacy workspace models when the flag is disabled', async () => {
    const wrapper = await mountForm({
      featureFlagEnabled: false,
      integration: {
        id: 5,
        type: 'ai',
        ai_settings: {
          openai: { models: ['integration-only-model', 'legacy-model'] },
        },
      },
      defaultValues: { integration_id: 5, ai_generative_ai_type: 'openai' },
    })
    await flushPromises()

    expect(wrapper.vm.availableModels).toEqual(['legacy-model'])
  })

  test('complete integration settings override the workspace models', async () => {
    const wrapper = await mountForm({
      featureFlagEnabled: true,
      integration: {
        id: 5,
        type: 'ai',
        ai_settings: {
          openai: { api_key: 'integration-key', models: ['blob-model'] },
        },
      },
      defaultValues: { integration_id: 5, ai_generative_ai_type: 'openai' },
    })
    await flushPromises()

    expect(wrapper.vm.availableModels).toEqual(['blob-model'])
  })

  test('limits partial integration model settings to workspace ai_agent models', async () => {
    const wrapper = await mountForm({
      featureFlagEnabled: true,
      integration: {
        id: 5,
        type: 'ai',
        ai_settings: {
          openai: { models: ['integration-only-model', 'db-model'] },
        },
      },
      defaultValues: { integration_id: 5, ai_generative_ai_type: 'openai' },
    })
    await flushPromises()

    expect(wrapper.find('[data-value="db-model"]').exists()).toBe(true)
    expect(wrapper.find('[data-value="integration-only-model"]').exists()).toBe(
      false
    )
  })

  test('keeps a stale model visible but marks it unavailable', async () => {
    const wrapper = await mountForm({
      featureFlagEnabled: true,
      integration: { id: 5, type: 'ai', ai_settings: {} },
      defaultValues: {
        integration_id: 5,
        ai_generative_ai_type: 'openai',
        ai_generative_ai_model: 'gone-model',
      },
    })
    await flushPromises()

    const staleOption = wrapper.get('[data-value="gone-model"]')
    expect(staleOption.attributes('aria-disabled')).toBe('true')
    expect(staleOption.text()).toContain('gone-model')

    const modelField = wrapper.get(
      '[data-label="aiAgentServiceForm.modelLabel"]'
    )
    expect(modelField.attributes('data-error')).toBe('true')
    expect(modelField.text()).toContain('selectAIModelForm.modelUnavailable')
  })

  test('keeps a stale provider visible while editing', async () => {
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

    expect(
      wrapper.vm.availableProviders.map((provider) => provider.type)
    ).toContain('anthropic')
  })

  test('marks a provider from an uninstalled extension as unavailable', async () => {
    const wrapper = await mountForm({
      featureFlagEnabled: true,
      integration: { id: 5, type: 'ai', ai_settings: {} },
      defaultValues: {
        integration_id: 5,
        ai_generative_ai_type: 'removed-provider',
        ai_generative_ai_model: 'removed-model',
      },
    })
    await flushPromises()

    expect(wrapper.get('[data-value="removed-model"]').exists()).toBe(true)
    expect(
      wrapper
        .get('[data-label="aiAgentServiceForm.modelLabel"]')
        .attributes('data-error')
    ).toBe('true')
  })

  test('re-validates the selection when switching integration with the flag enabled', async () => {
    // Mounted already "post-switch" to integration 6, with a model stale from integration 5.
    const wrapper = await mountForm({
      featureFlagEnabled: true,
      integration: {
        id: 6,
        type: 'ai',
        ai_settings: {
          openai: { api_key: 'integration-key', models: ['gpt-3.5'] },
        },
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

describe('AIAgentServiceType', () => {
  const makeServiceType = (integration = null) =>
    new AIAgentServiceType({
      app: {
        $featureFlagIsEnabled: () => true,
        $i18n: { t: (key) => key },
        $registry: { getAll: () => modelTypes },
        $store: {
          getters: {
            'integration/getIntegrationById': () => integration,
          },
        },
      },
    })

  const makeService = (model, integrationId = null) => ({
    integration_id: integrationId,
    ai_generative_ai_type: 'openai',
    ai_generative_ai_model: model,
    ai_prompt: { formula: 'Prompt' },
    ai_output_type: 'text',
  })

  test('reports a model unavailable to the workspace ai_agent feature', () => {
    const serviceType = makeServiceType()

    expect(
      serviceType.getErrorMessage({
        service: makeService('gone-model'),
        workspace,
      })
    ).toBe('serviceType.errorAIModelUnavailable')
    expect(
      serviceType.getErrorMessage({
        service: makeService('db-model'),
        workspace,
      })
    ).toBeNull()
  })

  test('uses a complete integration override when checking availability', () => {
    const application = { id: 1 }
    const serviceType = makeServiceType({
      id: 5,
      ai_settings: {
        openai: { api_key: 'integration-key', models: ['blob-model'] },
      },
    })
    expect(
      serviceType.getErrorMessage({
        service: makeService('blob-model', 5),
        workspace,
        application,
      })
    ).toBeNull()
  })

  test('reports a provider from an uninstalled extension as unavailable', () => {
    const serviceType = makeServiceType()

    expect(
      serviceType.getErrorMessage({
        service: {
          ...makeService('removed-model'),
          ai_generative_ai_type: 'removed-provider',
        },
        workspace,
      })
    ).toBe('serviceType.errorAIModelUnavailable')
  })
})
