import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

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
    expect(wrapper.text()).not.toContain('aiProviderAdmin.displayName')
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
      values: { model_identifier: 'claude-sonnet-5' },
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
      values: { model_identifier: 'custom-model' },
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
    expect(wrapper.text()).not.toContain('aiProviderAdmin.displayName')
    expect(dispatch).not.toHaveBeenCalledWith(
      'aiProvider/discoverModels',
      expect.anything()
    )
  })
})
