import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import AIProviderConfirmModal from '@baserow/modules/core/components/ai/AIProviderConfirmModal'
import AIProviderModelFeatureSelector from '@baserow/modules/core/components/ai/AIProviderModelFeatureSelector'
import AIProviderModelFormModal from '@baserow/modules/core/components/ai/AIProviderModelFormModal'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('AIProviderModelFormModal', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
    vi.restoreAllMocks()
  })

  const mountEditForm = async (usage, modelValues = {}) => {
    const dispatch = vi
      .spyOn(testApp.store, 'dispatch')
      .mockImplementation(async (action) => {
        if (action === 'aiProvider/fetchModelUsage') {
          return usage
        }
        if (action === 'aiProvider/updateModel') {
          return { id: 2, model_identifier: 'gpt-5.6' }
        }
      })
    const wrapper = await testApp.mount(AIProviderModelFormModal, {
      props: {
        provider: { id: 1, provider_type: 'openai', models: [] },
        model: {
          id: 2,
          model_identifier: 'gpt-5.6',
          feature_types: ['ai_agent', 'ai_fields', 'kuma'],
          ...modelValues,
        },
      },
    })
    await wrapper.vm.show()
    await flushPromises()
    return { wrapper, dispatch }
  }

  const uncheckFeatures = async (wrapper, featureTypes) => {
    wrapper
      .findComponent(AIProviderModelFeatureSelector)
      .vm.$emit('update:modelValue', featureTypes)
    await flushPromises()
  }

  test('confirms before saving when a feature in use is unchecked', async () => {
    const { wrapper, dispatch } = await mountEditForm({
      usage: [
        { featureType: 'ai_fields', count: 2 },
        { featureType: 'ai_agent', count: 0 },
      ],
      blockingFeatureTypes: [],
    })
    await uncheckFeatures(wrapper, ['ai_agent', 'kuma'])

    await wrapper.find('.actions button').trigger('click')
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith('aiProvider/fetchModelUsage', {
      modelId: 2,
    })
    expect(dispatch).not.toHaveBeenCalledWith(
      'aiProvider/updateModel',
      expect.anything()
    )
    const confirmModal = wrapper.findComponent(AIProviderConfirmModal)
    expect(confirmModal.props('title')).toBe(
      'aiProviderAdmin.modelFeaturesRemovedTitle'
    )
    expect(confirmModal.props('message')).toMatch(
      /^aiProviderAdmin\.modelInUse.* aiProviderAdmin\.modelFeaturesRemovedDescription$/
    )

    confirmModal.vm.$emit('confirm')
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith('aiProvider/updateModel', {
      modelId: 2,
      values: {
        model_identifier: 'gpt-5.6',
        feature_types: ['ai_agent', 'kuma'],
      },
    })
  })

  test('saves without a confirmation when the unchecked feature is unused', async () => {
    const { wrapper, dispatch } = await mountEditForm({
      usage: [
        { featureType: 'ai_fields', count: 2 },
        { featureType: 'ai_agent', count: 0 },
      ],
      blockingFeatureTypes: [],
    })
    await uncheckFeatures(wrapper, ['ai_fields', 'kuma'])

    await wrapper.find('.actions button').trigger('click')
    await flushPromises()

    expect(wrapper.findComponent(AIProviderConfirmModal).exists()).toBe(false)
    expect(dispatch).toHaveBeenCalledWith('aiProvider/updateModel', {
      modelId: 2,
      values: {
        model_identifier: 'gpt-5.6',
        feature_types: ['ai_fields', 'kuma'],
      },
    })
  })

  test('does not look up usage when no feature is unchecked', async () => {
    const { wrapper, dispatch } = await mountEditForm({
      usage: [{ featureType: 'ai_fields', count: 2 }],
      blockingFeatureTypes: [],
    })

    await wrapper.find('.actions button').trigger('click')
    await flushPromises()

    expect(dispatch).not.toHaveBeenCalledWith(
      'aiProvider/fetchModelUsage',
      expect.anything()
    )
    expect(dispatch).toHaveBeenCalledWith('aiProvider/updateModel', {
      modelId: 2,
      values: {
        model_identifier: 'gpt-5.6',
        feature_types: ['ai_agent', 'ai_fields', 'kuma'],
      },
    })
  })

  test('saves when the usage lookup fails', async () => {
    const dispatch = vi
      .spyOn(testApp.store, 'dispatch')
      .mockImplementation(async (action) => {
        if (action === 'aiProvider/fetchModelUsage') {
          throw new Error('Usage unavailable')
        }
      })
    const wrapper = await testApp.mount(AIProviderModelFormModal, {
      props: {
        provider: { id: 1, provider_type: 'openai', models: [] },
        model: {
          id: 2,
          model_identifier: 'gpt-5.6',
          feature_types: ['ai_agent', 'ai_fields', 'kuma'],
        },
      },
    })
    await wrapper.vm.show()
    await uncheckFeatures(wrapper, ['ai_agent', 'kuma'])

    await wrapper.find('.actions button').trigger('click')
    await flushPromises()

    expect(wrapper.findComponent(AIProviderConfirmModal).exists()).toBe(false)
    expect(dispatch).toHaveBeenCalledWith('aiProvider/updateModel', {
      modelId: 2,
      values: {
        model_identifier: 'gpt-5.6',
        feature_types: ['ai_agent', 'kuma'],
      },
    })
  })

  test('confirms a rename while consumers still point at the old identifier', async () => {
    const { wrapper, dispatch } = await mountEditForm({
      usage: [
        { featureType: 'ai_fields', count: 2 },
        { featureType: 'ai_agent', count: 1 },
      ],
      blockingFeatureTypes: [],
    })
    wrapper.vm.values.model_identifier = 'gpt-5.7'
    await flushPromises()

    await wrapper.find('.actions button').trigger('click')
    await flushPromises()

    expect(dispatch).not.toHaveBeenCalledWith(
      'aiProvider/updateModel',
      expect.anything()
    )
    const confirmModal = wrapper.findComponent(AIProviderConfirmModal)
    expect(confirmModal.props('title')).toBe(
      'aiProviderAdmin.modelIdentifierRenamedTitle'
    )
    expect(confirmModal.props('message')).toMatch(
      /^aiProviderAdmin\.modelInUse.* aiProviderAdmin\.modelIdentifierRenamedDescription$/
    )

    confirmModal.vm.$emit('confirm')
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith('aiProvider/updateModel', {
      modelId: 2,
      values: {
        model_identifier: 'gpt-5.7',
        feature_types: ['ai_agent', 'ai_fields', 'kuma'],
      },
    })
  })

  test('saves a rename nothing depends on without a confirmation', async () => {
    const { wrapper, dispatch } = await mountEditForm({
      usage: [{ featureType: 'ai_fields', count: 0 }],
      blockingFeatureTypes: [],
    })
    wrapper.vm.values.model_identifier = 'gpt-5.7'
    await flushPromises()

    await wrapper.find('.actions button').trigger('click')
    await flushPromises()

    expect(wrapper.findComponent(AIProviderConfirmModal).exists()).toBe(false)
    expect(dispatch).toHaveBeenCalledWith('aiProvider/updateModel', {
      modelId: 2,
      values: {
        model_identifier: 'gpt-5.7',
        feature_types: ['ai_agent', 'ai_fields', 'kuma'],
      },
    })
  })

  test('keeps the confirmation open across a re-render and closes both on save', async () => {
    const { wrapper, dispatch } = await mountEditForm({
      usage: [{ featureType: 'ai_fields', count: 2 }],
      blockingFeatureTypes: [],
    })
    await uncheckFeatures(wrapper, ['ai_agent', 'kuma'])
    await wrapper.find('.actions button').trigger('click')
    await flushPromises()

    const confirmModal = wrapper.findComponent(AIProviderConfirmModal)
    const uid = confirmModal.vm.$.uid
    expect(confirmModal.vm.$refs.modal.open).toBe(true)

    wrapper.vm.loading = true
    await flushPromises()
    wrapper.vm.loading = false
    await flushPromises()

    const reRendered = wrapper.findComponent(AIProviderConfirmModal)
    expect(reRendered.vm.$.uid).toBe(uid)
    expect(reRendered.vm.$refs.modal.open).toBe(true)

    reRendered.vm.$emit('confirm')
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith(
      'aiProvider/updateModel',
      expect.anything()
    )
    expect(wrapper.emitted('saved')).toBeTruthy()
    expect(wrapper.vm.$refs.modal.open).toBe(false)
    expect(document.body.classList.contains('prevent-scroll')).toBe(false)
  })

  test('shows discovered models, excludes configured models, and accepts a suggestion', async () => {
    const dispatch = vi
      .spyOn(testApp.store, 'dispatch')
      .mockImplementation((action) => {
        if (action === 'aiProvider/discoverModels') {
          return Promise.resolve({
            models: ['configured-model', 'claude-sonnet-5', 'claude-opus-4-8'],
            supported: true,
          })
        }
        if (action === 'aiProvider/createModel') {
          return Promise.resolve({
            id: 2,
            model_identifier: 'claude-sonnet-5',
          })
        }
        return Promise.resolve()
      })
    const wrapper = await testApp.mount(AIProviderModelFormModal, {
      props: {
        provider: {
          id: 1,
          provider_type: 'anthropic',
          models: [{ model_identifier: 'configured-model' }],
        },
      },
    })
    await flushPromises()
    await wrapper.vm.show()
    expect(dispatch).not.toHaveBeenCalledWith(
      'aiProvider/discoverModels',
      expect.anything()
    )
    await wrapper
      .find('.ai-provider-model-combobox .form-input__input')
      .trigger('focus')
    await flushPromises()

    expect(wrapper.find('.control__helper-text').text()).toBe(
      'generativeAIModelType.anthropicModelIdentifierDescription'
    )
    expect(dispatch).toHaveBeenCalledWith(
      'aiProvider/discoverModels',
      'anthropic'
    )
    expect(
      wrapper
        .findAll('.ai-provider-model-combobox__suggestion')
        .map((suggestion) => suggestion.text())
    ).toEqual(['claude-sonnet-5', 'claude-opus-4-8'])

    await wrapper
      .findAll('.ai-provider-model-combobox__suggestion')[0]
      .trigger('click')

    expect(
      wrapper.find('.ai-provider-model-combobox .form-input__input').element
        .value
    ).toBe('claude-sonnet-5')

    await wrapper.find('.actions button').trigger('click')
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith('aiProvider/createModel', {
      providerId: 1,
      values: {
        model_identifier: 'claude-sonnet-5',
        feature_types: ['ai_agent', 'ai_fields', 'kuma'],
      },
    })
    expect(dispatch).not.toHaveBeenCalledWith(
      'aiProvider/testModels',
      expect.anything()
    )
  })

  test('keeps manual entry available when discovery fails', async () => {
    vi.spyOn(testApp.store, 'dispatch').mockRejectedValue(
      new Error('Discovery failed')
    )
    const wrapper = await testApp.mount(AIProviderModelFormModal, {
      props: {
        provider: { id: 1, provider_type: 'openai', models: [] },
      },
    })
    await flushPromises()
    await wrapper.vm.show()
    const input = wrapper.find('.ai-provider-model-combobox .form-input__input')
    await input.trigger('focus')
    await flushPromises()

    expect(wrapper.find('.select__items--empty').text()).toBe(
      'aiProviderAdmin.modelDiscoveryUnavailable'
    )

    await input.trigger('focus')
    await flushPromises()
    expect(testApp.store.dispatch).toHaveBeenCalledTimes(2)

    await input.setValue('custom-compatible-model')
    await flushPromises()

    expect(input.element.value).toBe('custom-compatible-model')
    expect(wrapper.find('.actions button').attributes('disabled')).toBe(
      undefined
    )
  })

  test('does not automatically test a custom model identifier', async () => {
    const dispatch = vi
      .spyOn(testApp.store, 'dispatch')
      .mockImplementation((action) => {
        if (action === 'aiProvider/discoverModels') {
          return Promise.resolve({ models: ['gpt-5.6'], supported: true })
        }
        if (action === 'aiProvider/createModel') {
          return Promise.resolve({
            id: 2,
            model_identifier: 'custom-model',
          })
        }
        return Promise.resolve()
      })
    const wrapper = await testApp.mount(AIProviderModelFormModal, {
      props: {
        provider: { id: 1, provider_type: 'openai', models: [] },
      },
    })
    await flushPromises()
    await wrapper.vm.show()
    const modelInput = wrapper.find(
      '.ai-provider-model-combobox .form-input__input'
    )
    await modelInput.trigger('focus')
    await flushPromises()
    await modelInput.setValue('custom-model')
    await wrapper.find('.actions button').trigger('click')
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith('aiProvider/createModel', {
      providerId: 1,
      values: {
        model_identifier: 'custom-model',
        feature_types: ['ai_agent', 'ai_fields', 'kuma'],
      },
    })
    expect(dispatch).not.toHaveBeenCalledWith(
      'aiProvider/testModels',
      expect.anything()
    )
  })

  test('does not discover models while editing an existing model', async () => {
    const dispatch = vi.spyOn(testApp.store, 'dispatch')
    const wrapper = await testApp.mount(AIProviderModelFormModal, {
      props: {
        provider: { id: 1, provider_type: 'mistral', models: [] },
        model: {
          id: 2,
          model_identifier: 'mistral-large-latest',
        },
      },
    })
    await flushPromises()
    await wrapper.vm.show()

    expect(wrapper.find('.ai-provider-model-combobox').exists()).toBe(false)
    expect(dispatch).not.toHaveBeenCalledWith(
      'aiProvider/discoverModels',
      expect.anything()
    )
  })

  test('shows and clears a duplicate identifier error on the model field', async () => {
    const dispatch = vi
      .spyOn(testApp.store, 'dispatch')
      .mockImplementation((action) => {
        if (action === 'aiProvider/createModel') {
          return Promise.reject({
            response: {
              data: {
                error: 'ERROR_AI_PROVIDER_MODEL_ALREADY_CONFIGURED',
                detail:
                  'That model identifier is already configured for this provider.',
              },
            },
          })
        }
        return Promise.resolve()
      })
    const wrapper = await testApp.mount(AIProviderModelFormModal, {
      props: {
        provider: { id: 1, provider_type: 'openai', models: [] },
      },
    })
    await wrapper.vm.show()
    const modelInput = wrapper.find(
      '.ai-provider-model-combobox .form-input__input'
    )
    await modelInput.setValue('gpt-5.4')
    await wrapper.find('.actions button').trigger('click')
    await flushPromises()

    const modelField = wrapper.find('.control')
    expect(modelField.find('.control__messages--error').text()).toBe(
      'That model identifier is already configured for this provider.'
    )
    expect(modelField.find('.form-input').classes()).toContain(
      'form-input--error'
    )
    const fieldContentOrder = modelField
      .findAll(
        '.form-input, .control__messages--error, .ai-provider-form__hint, .control__helper-text'
      )
      .map((element) =>
        [
          'form-input',
          'control__messages--error',
          'ai-provider-form__hint',
          'control__helper-text',
        ].find((className) => element.classes().includes(className))
      )
    expect(fieldContentOrder).toEqual([
      'form-input',
      'control__messages--error',
      'ai-provider-form__hint',
      'control__helper-text',
    ])
    expect(dispatch).not.toHaveBeenCalledWith('toast/error', expect.anything())

    await wrapper
      .find('.ai-provider-model-combobox .form-input__input')
      .setValue('gpt-5.4-mini')
    await flushPromises()
    expect(wrapper.find('.control__messages--error').exists()).toBe(false)
    expect(wrapper.find('.form-input').classes()).not.toContain(
      'form-input--error'
    )
  })
})
