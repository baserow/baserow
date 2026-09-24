import { defineComponent, reactive, ref, unref } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { enableAutoUnmount, flushPromises } from '@vue/test-utils'

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
  emits: ['update:modelValue'],
  template:
    '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
})
const DropdownItemStub = defineComponent({
  name: 'DropdownItem',
  props: {
    name: { type: String, required: true },
    value: { type: String, required: true },
    disabled: { type: Boolean, default: false },
  },
  template:
    '<option :value="value" :data-value="value" :disabled="disabled" :aria-disabled="disabled">{{ name }}</option>',
})
const IntegrationDropdownStub = defineComponent({
  name: 'IntegrationDropdown',
  props: {
    modelValue: { type: Number, default: null },
    integrations: { type: Array, required: true },
  },
  emits: ['update:modelValue'],
  template:
    '<select :value="modelValue" @change="$emit(\'update:modelValue\', Number($event.target.value))"><option v-for="integration in integrations" :key="integration.id" :value="integration.id">{{ integration.id }}</option></select>',
})
const PassthroughStub = defineComponent({ template: '<div />' })

enableAutoUnmount(afterEach)

const openAIModelType = {
  getType: () => 'openai',
  getName: () => 'OpenAI',
  getMaxTemperature: () => 2,
  isIntegrationSettingsComplete: (settings) => Boolean(settings.api_key),
  isBuiltInProviderType: () => true,
}
const anthropicModelType = {
  getType: () => 'anthropic',
  getName: () => 'Anthropic',
  getMaxTemperature: () => 1,
  isIntegrationSettingsComplete: (settings) => Boolean(settings.api_key),
  isBuiltInProviderType: () => true,
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
  integrations = [integration],
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
        IntegrationDropdown: IntegrationDropdownStub,
        InjectedFormulaInput: PassthroughStub,
        RadioGroup: PassthroughStub,
        FormInput: PassthroughStub,
        Button: PassthroughStub,
      },
      mocks: {
        $t: (key) => key,
        $featureFlagIsEnabled: () => unref(featureFlagEnabled),
        $store: {
          getters: {
            'integration/getIntegrations': () => integrations,
            'integration/getIntegrationById': (application, id) =>
              integrations.find((candidate) => candidate.id === id),
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

    expect(wrapper.find('[data-value="db-model"]').exists()).toBe(true)
    expect(wrapper.find('[data-value="legacy-model"]').exists()).toBe(false)
  })

  test('lists legacy workspace models when the flag is disabled', async () => {
    const wrapper = await mountForm({
      featureFlagEnabled: false,
      integration: { id: 5, type: 'ai', ai_settings: {} },
      defaultValues: { integration_id: 5, ai_generative_ai_type: 'openai' },
    })
    await flushPromises()

    expect(wrapper.find('[data-value="legacy-model"]').exists()).toBe(true)
    expect(wrapper.find('[data-value="db-model"]').exists()).toBe(false)
  })

  test('preserves the selected model through flag activation and availability changes', async () => {
    const featureFlagEnabled = ref(false)
    const workspaceValue = reactive({
      ...workspace,
      ai_features: { ai_agent: { models: { openai: ['db-model'] } } },
    })
    const wrapper = await mountForm({
      featureFlagEnabled,
      workspace: workspaceValue,
      integration: { id: 5, type: 'ai', ai_settings: {} },
      defaultValues: {
        integration_id: 5,
        ai_generative_ai_type: 'openai',
        ai_generative_ai_model: 'legacy-model',
      },
    })
    await flushPromises()

    const modelField = wrapper.get(
      '[data-label="aiAgentServiceForm.modelLabel"]'
    )
    expect(modelField.get('select').element.value).toBe('legacy-model')
    expect(modelField.attributes('data-error')).toBe('false')

    featureFlagEnabled.value = true
    await flushPromises()

    expect(modelField.get('select').element.value).toBe('legacy-model')
    expect(modelField.attributes('data-error')).toBe('true')
    expect(
      modelField.get('[data-value="legacy-model"]').attributes('aria-disabled')
    ).toBe('true')
    expect(modelField.get('[data-value="db-model"]').exists()).toBe(true)

    workspaceValue.ai_features.ai_agent.models.openai.push('legacy-model')
    await flushPromises()

    expect(modelField.get('select').element.value).toBe('legacy-model')
    expect(modelField.attributes('data-error')).toBe('false')
    expect(
      modelField.get('[data-value="legacy-model"]').attributes('aria-disabled')
    ).toBe('false')

    featureFlagEnabled.value = false
    await flushPromises()

    expect(modelField.get('select').element.value).toBe('legacy-model')
    expect(modelField.find('[data-value="db-model"]').exists()).toBe(false)
    expect(modelField.attributes('data-error')).toBe('false')
  })

  test('marks a selected model unavailable when its feature eligibility is removed', async () => {
    const workspaceValue = reactive({
      ...workspace,
      ai_features: { ai_agent: { models: { openai: ['db-model'] } } },
    })
    const wrapper = await mountForm({
      featureFlagEnabled: true,
      workspace: workspaceValue,
      integration: { id: 5, type: 'ai', ai_settings: {} },
      defaultValues: {
        integration_id: 5,
        ai_generative_ai_type: 'openai',
        ai_generative_ai_model: 'db-model',
      },
    })
    await flushPromises()

    workspaceValue.ai_features.ai_agent.models = {}
    await flushPromises()

    const modelField = wrapper.get(
      '[data-label="aiAgentServiceForm.modelLabel"]'
    )
    expect(modelField.get('select').element.value).toBe('db-model')
    expect(modelField.attributes('data-error')).toBe('true')
    expect(modelField.text()).toContain('selectAIModelForm.modelUnavailable')
    expect(modelField.find('[data-value="legacy-model"]').exists()).toBe(false)
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

    expect(wrapper.find('[data-value="legacy-model"]').exists()).toBe(true)
    expect(wrapper.find('[data-value="integration-only-model"]').exists()).toBe(
      false
    )
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

    expect(wrapper.find('[data-value="blob-model"]').exists()).toBe(true)
    expect(wrapper.find('[data-value="db-model"]').exists()).toBe(false)
  })

  test.each([
    {
      featureFlagEnabled: true,
      available: 'db-model',
      excluded: 'legacy-model',
    },
    {
      featureFlagEnabled: false,
      available: 'legacy-model',
      excluded: 'db-model',
    },
  ])(
    'inherits available models for an own-key override without models when flag is $featureFlagEnabled',
    async ({ featureFlagEnabled, available, excluded }) => {
      const wrapper = await mountForm({
        featureFlagEnabled,
        integration: {
          id: 5,
          type: 'ai',
          ai_settings: { openai: { api_key: 'integration-key' } },
        },
        defaultValues: {
          integration_id: 5,
          ai_generative_ai_type: 'openai',
          ai_generative_ai_model: available,
        },
      })
      await flushPromises()

      expect(
        wrapper.get(`[data-value="${available}"]`).attributes('aria-disabled')
      ).toBe('false')
      expect(wrapper.find(`[data-value="${excluded}"]`).exists()).toBe(false)
      expect(
        wrapper
          .get('[data-label="aiAgentServiceForm.modelLabel"]')
          .attributes('data-error')
      ).toBe('false')
    }
  )

  test.each([true, false])(
    'keeps an explicit empty own-key model list empty when flag is %s',
    async (featureFlagEnabled) => {
      const wrapper = await mountForm({
        featureFlagEnabled,
        integration: {
          id: 5,
          type: 'ai',
          ai_settings: { openai: { api_key: 'integration-key', models: [] } },
        },
        defaultValues: { integration_id: 5, ai_generative_ai_type: 'openai' },
      })
      await flushPromises()

      expect(wrapper.find('[data-value="db-model"]').exists()).toBe(false)
      expect(wrapper.find('[data-value="legacy-model"]').exists()).toBe(false)
    }
  )

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

    expect(wrapper.get('[data-value="anthropic"]').text()).toBe('Anthropic')
  })

  test('marks a provider from an uninstalled extension as unavailable', async () => {
    const wrapper = await mountForm({
      featureFlagEnabled: true,
      integration: { id: 5, type: 'ai', ai_settings: {} },
      workspace: {
        ...workspace,
        ai_features: {
          ai_agent: { models: { 'removed-provider': ['removed-model'] } },
        },
      },
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
    const wrapper = await mountForm({
      featureFlagEnabled: true,
      integrations: [
        {
          id: 5,
          type: 'ai',
          ai_settings: {
            openai: { api_key: 'first-key', models: ['gpt-4'] },
          },
        },
        {
          id: 6,
          type: 'ai',
          ai_settings: {
            openai: { api_key: 'second-key', models: ['gpt-3.5'] },
          },
        },
      ],
      defaultValues: {
        integration_id: 5,
        ai_generative_ai_type: 'openai',
        ai_generative_ai_model: 'gpt-4',
      },
    })
    await flushPromises()

    await wrapper
      .get('[data-label="aiAgentServiceForm.integrationLabel"] select')
      .setValue('6')
    await flushPromises()

    expect(
      wrapper.get('[data-label="aiAgentServiceForm.modelLabel"] select').element
        .value
    ).toBe('gpt-3.5')
    expect(wrapper.find('[data-value="gpt-4"]').exists()).toBe(false)
  })
})

describe('AIAgentServiceType', () => {
  const makeServiceType = (integration = null, featureFlagEnabled = true) =>
    new AIAgentServiceType({
      app: {
        $featureFlagIsEnabled: () => featureFlagEnabled,
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

  test('does not enforce database model availability when the flag is disabled', () => {
    const serviceType = makeServiceType(null, false)

    expect(
      serviceType.getErrorMessage({
        service: makeService('legacy-model'),
        workspace,
      })
    ).toBeNull()
  })

  test('defers availability validation until the integration is loaded', () => {
    const application = { id: 1 }
    const serviceType = makeServiceType()

    expect(
      serviceType.getErrorMessage({
        service: makeService('blob-model', 5),
        workspace,
        application,
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

  test('validates an own-key override without models against the ai_agent allowlist', () => {
    const application = { id: 1 }
    const serviceType = makeServiceType({
      id: 5,
      ai_settings: { openai: { api_key: 'integration-key' } },
    })

    expect(
      serviceType.getErrorMessage({
        service: makeService('db-model', 5),
        workspace,
        application,
      })
    ).toBeNull()
    expect(
      serviceType.getErrorMessage({
        service: makeService('legacy-model', 5),
        workspace,
        application,
      })
    ).toBe('serviceType.errorAIModelUnavailable')
  })

  test('reports a provider from an uninstalled extension as unavailable', () => {
    const serviceType = makeServiceType()

    expect(
      serviceType.getErrorMessage({
        service: {
          ...makeService('removed-model'),
          ai_generative_ai_type: 'removed-provider',
        },
        workspace: {
          ...workspace,
          ai_features: {
            ai_agent: { models: { 'removed-provider': ['removed-model'] } },
          },
        },
      })
    ).toBe('serviceType.errorAIModelUnavailable')
  })
})
