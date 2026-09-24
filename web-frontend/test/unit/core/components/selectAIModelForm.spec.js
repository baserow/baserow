import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { enableAutoUnmount, flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, test, vi } from 'vitest'

import SelectAIModelForm from '@baserow/modules/core/components/ai/SelectAIModelForm'

const FormGroupStub = defineComponent({
  name: 'FormGroup',
  props: {
    label: { type: String, default: null },
    error: { type: Boolean, default: false },
  },
  template:
    '<div class="form-group" :data-label="label" :data-error="error"><slot /><slot name="error" /></div>',
})
const DropdownStub = defineComponent({
  name: 'Dropdown',
  props: { modelValue: { type: [String, Number], default: null } },
  emits: ['update:modelValue'],
  methods: {
    select(value) {
      this.$emit('update:modelValue', value === undefined ? null : value)
    },
  },
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
const PassthroughStub = defineComponent({ template: '<div />' })

enableAutoUnmount(afterEach)

const openAIModelType = {
  getType: () => 'openai',
  getName: () => 'OpenAI',
  getMaxTemperature: () => 2,
}
const anthropicModelType = {
  getType: () => 'anthropic',
  getName: () => 'Anthropic',
  getMaxTemperature: () => 1,
}
const modelTypes = { openai: openAIModelType, anthropic: anthropicModelType }

const workspace = {
  id: 1,
  generative_ai_models_enabled: { openai: ['legacy-model'] },
  ai_features: { ai_fields: { models: { openai: ['gpt-4'] } } },
}

async function mountForm({
  featureFlagEnabled = true,
  defaultValues = {},
  workspace: workspaceValue = workspace,
} = {}) {
  const wrapper = await mountSuspended(SelectAIModelForm, {
    props: {
      database: { id: 100, workspace: { id: 1 } },
      featureType: 'ai_fields',
      defaultValues,
    },
    global: {
      stubs: {
        FormGroup: FormGroupStub,
        Dropdown: DropdownStub,
        DropdownItem: DropdownItemStub,
        FormInput: PassthroughStub,
      },
      mocks: {
        $t: (key) => key,
        $featureFlagIsEnabled: () => featureFlagEnabled,
        $store: {
          dispatch: vi.fn().mockResolvedValue(undefined),
          getters: {
            'workspace/get': () => workspaceValue,
            'settings/get': () => ({}),
          },
        },
        $registry: {
          getAll: () => modelTypes,
          get: (namespace, type) => modelTypes[type],
        },
      },
    },
  })
  await flushPromises()
  return wrapper
}

const typeField = (wrapper) =>
  wrapper.get('[data-label="selectAIModelForm.AIType"]')
const modelField = (wrapper) =>
  wrapper.get('[data-label="selectAIModelForm.AIModel"]')

describe('SelectAIModelForm', () => {
  test('keeps a saved model that is no longer available visible and invalid', async () => {
    const wrapper = await mountForm({
      defaultValues: {
        ai_generative_ai_type: 'openai',
        ai_generative_ai_model: 'retired-model',
      },
    })

    const field = modelField(wrapper)
    expect(field.get('select').element.value).toBe('retired-model')
    expect(
      field.get('[data-value="retired-model"]').attributes('aria-disabled')
    ).toBe('true')
    expect(field.get('[data-value="gpt-4"]').exists()).toBe(true)
    expect(field.attributes('data-error')).toBe('true')
    expect(field.text()).toContain('selectAIModelForm.modelUnavailable')

    wrapper.vm.touch()
    expect(wrapper.vm.isFormValid()).toBe(false)
  })

  test('keeps a saved provider that is no longer available visible', async () => {
    const wrapper = await mountForm({
      defaultValues: {
        ai_generative_ai_type: 'anthropic',
        ai_generative_ai_model: 'claude',
      },
    })

    const field = typeField(wrapper)
    expect(field.get('select').element.value).toBe('anthropic')
    expect(field.get('[data-value="anthropic"]').text()).toBe('Anthropic')
    expect(field.get('[data-value="openai"]').text()).toBe('OpenAI')
  })

  test('names a saved provider the registry no longer knows by its type', async () => {
    const wrapper = await mountForm({
      defaultValues: {
        ai_generative_ai_type: 'removed-provider',
        ai_generative_ai_model: 'removed-model',
      },
    })

    expect(
      typeField(wrapper).get('[data-value="removed-provider"]').text()
    ).toBe('removed-provider')
    expect(
      modelField(wrapper).get('[data-value="removed-model"]').exists()
    ).toBe(true)
  })

  test('leaves an available selection untouched', async () => {
    const wrapper = await mountForm({
      defaultValues: {
        ai_generative_ai_type: 'openai',
        ai_generative_ai_model: 'gpt-4',
      },
    })

    const field = modelField(wrapper)
    expect(field.findAll('option').map((option) => option.text())).toEqual([
      'gpt-4',
    ])
    expect(field.get('[data-value="gpt-4"]').attributes('aria-disabled')).toBe(
      'false'
    )
    expect(field.attributes('data-error')).toBe('false')
    expect(field.text()).not.toContain('selectAIModelForm.modelUnavailable')

    wrapper.vm.touch()
    expect(wrapper.vm.isFormValid()).toBe(true)
  })

  test('selects the first available type and model for an empty form', async () => {
    const wrapper = await mountForm()

    expect(wrapper.vm.values.ai_generative_ai_type).toBe('openai')
    expect(wrapper.vm.values.ai_generative_ai_model).toBe('gpt-4')
  })

  test('does not retain an unavailable model when the flag is disabled', async () => {
    const wrapper = await mountForm({
      featureFlagEnabled: false,
      defaultValues: {
        ai_generative_ai_type: 'openai',
        ai_generative_ai_model: 'retired-model',
      },
    })

    const field = modelField(wrapper)
    expect(field.findAll('option').map((option) => option.text())).toEqual([
      'legacy-model',
    ])
    expect(field.attributes('data-error')).toBe('false')

    wrapper.vm.touch()
    expect(wrapper.vm.isFormValid()).toBe(false)
  })
})
