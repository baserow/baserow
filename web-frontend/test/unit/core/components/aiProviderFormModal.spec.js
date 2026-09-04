import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import AIProviderFormModal from '@baserow/modules/core/components/ai/AIProviderFormModal'
import { TestApp } from '@baserow/test/helpers/testApp'

function makeContext({ apiKeyEditing = false, apiKey = '' } = {}) {
  const dispatch = vi.fn().mockResolvedValue({ id: 1 })
  return {
    provider: {
      id: 1,
      provider_type: 'openai',
    },
    apiKeyEditing,
    loading: false,
    values: { provider_type: 'openai', api_key: apiKey },
    extraSettings: {},
    models: [],
    selectedType: { type: 'openai', uses_api_key: true },
    getExtraSettings: () => ({}),
    $store: { dispatch },
    $emit: vi.fn(),
    $t: (key) => key,
    hide: vi.fn(),
  }
}

describe('AIProviderFormModal', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
    vi.restoreAllMocks()
  })

  test('loads suggestions and creates a provider without pre-save testing', async () => {
    const dispatch = vi
      .spyOn(testApp.store, 'dispatch')
      .mockImplementation((action) => {
        if (action === 'aiProvider/discoverModels') {
          return Promise.resolve({
            models: ['gpt-5.6', 'gpt-5.6-terra'],
            supported: true,
          })
        }
        if (action === 'aiProvider/create') {
          return Promise.resolve({
            id: 1,
            models: [{ id: 11, model_identifier: 'gpt-5.6' }],
          })
        }
        return Promise.resolve({ id: 1 })
      })
    const wrapper = await testApp.mount(AIProviderFormModal, {
      props: {
        providerTypes: [
          {
            type: 'openai',
            name: 'OpenAI',
            uses_api_key: true,
            extra_fields: [
              { name: 'base_url', required: false, allow_blank: true },
            ],
          },
        ],
      },
    })
    await wrapper.vm.show()

    const removeModelButton = wrapper.find(
      '.ai-provider-form__model-row .button'
    )
    expect(removeModelButton.classes()).toContain('button--regular')
    expect(removeModelButton.classes()).not.toContain('button--small')

    const helperText = wrapper
      .findAll('.control__helper-text')
      .map((helper) => helper.text())

    expect(helperText).toEqual([
      'generativeAIModelType.openaiApiKeyDescription',
      'generativeAIModelType.openaiBaseUrlDescription',
      'generativeAIModelType.openaiModelIdentifierDescription',
    ])

    const modelInput = wrapper.find(
      '.ai-provider-model-combobox .form-input__input'
    )
    await modelInput.trigger('focus')
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith('aiProvider/discoverModels', 'openai')
    await modelInput.trigger('focus')
    await flushPromises()
    expect(
      dispatch.mock.calls.filter(
        ([action]) => action === 'aiProvider/discoverModels'
      )
    ).toHaveLength(1)
    expect(
      wrapper
        .findAll('.ai-provider-model-combobox__suggestion')
        .map((suggestion) => suggestion.text())
    ).toEqual(['gpt-5.6', 'gpt-5.6-terra'])

    await wrapper
      .findAll('.ai-provider-model-combobox__suggestion')[0]
      .trigger('click')
    await wrapper.find('input[type="password"]').setValue('temporary-secret')

    expect(
      wrapper
        .findAll('button')
        .some((button) => button.text() === 'aiProviderAdmin.test')
    ).toBe(false)
    expect(wrapper.find('.ai-provider-form__model-status').exists()).toBe(false)

    await wrapper.find('.actions button').trigger('click')
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith('aiProvider/create', {
      extra_settings: {},
      provider_type: 'openai',
      api_key: 'temporary-secret',
      models: [
        {
          model_identifier: 'gpt-5.6',
          feature_types: ['ai_agent', 'ai_fields', 'kuma'],
        },
      ],
    })
    expect(
      dispatch.mock.calls.filter(
        ([action]) => action === 'aiProvider/testModels'
      )
    ).toHaveLength(0)
  })

  test('keeps manual entry available after suggestions fail and does not test it', async () => {
    const dispatch = vi
      .spyOn(testApp.store, 'dispatch')
      .mockImplementation((action) => {
        if (action === 'aiProvider/discoverModels') {
          return Promise.reject(new Error('Suggestions failed'))
        }
        if (action === 'aiProvider/create') {
          return Promise.resolve({
            id: 1,
            models: [{ id: 12, model_identifier: 'custom-model' }],
          })
        }
        return Promise.resolve()
      })
    const wrapper = await testApp.mount(AIProviderFormModal, {
      props: {
        providerTypes: [
          {
            type: 'openai',
            name: 'OpenAI',
            uses_api_key: true,
            extra_fields: [],
          },
        ],
      },
    })
    await wrapper.vm.show()
    const modelInput = wrapper.find(
      '.ai-provider-model-combobox .form-input__input'
    )
    await modelInput.trigger('focus')
    await flushPromises()

    await modelInput.trigger('focus')
    await flushPromises()
    expect(
      dispatch.mock.calls.filter(
        ([action]) => action === 'aiProvider/discoverModels'
      )
    ).toHaveLength(2)

    await modelInput.setValue('custom-model')
    await wrapper.find('input[type="password"]').setValue('valid-secret')
    await wrapper.find('.actions button').trigger('click')
    await flushPromises()

    expect(dispatch).not.toHaveBeenCalledWith(
      'aiProvider/testModels',
      expect.anything()
    )
  })

  test('editing settings omits the hidden name and unchanged api_key', async () => {
    const context = makeContext()

    await AIProviderFormModal.methods.submit.call(context)

    expect(context.$store.dispatch).toHaveBeenCalledWith('aiProvider/update', {
      providerId: 1,
      values: { extra_settings: {} },
    })
  })

  test('replaces an existing api key without showing redundant key status', async () => {
    const dispatch = vi.spyOn(testApp.store, 'dispatch').mockResolvedValue({
      id: 1,
      provider_type: 'openai',
      extra_settings: {},
      models: [],
    })
    const wrapper = await testApp.mount(AIProviderFormModal, {
      props: {
        provider: {
          id: 1,
          provider_type: 'openai',
          extra_settings: {},
        },
        providerTypes: [
          {
            type: 'openai',
            name: 'OpenAI',
            uses_api_key: true,
            extra_fields: [],
          },
        ],
      },
    })
    await wrapper.vm.show()

    expect(wrapper.find('input[type="password"]').exists()).toBe(false)

    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'aiProviderAdmin.changeApiKey')
      .trigger('click')

    const passwordInput = wrapper.find('input[type="password"]')
    expect(passwordInput.exists()).toBe(true)
    expect(wrapper.find('.actions button').attributes('disabled')).toBeDefined()

    await passwordInput.setValue('replacement-secret')
    await flushPromises()
    const saveButton = wrapper.find('.actions button')
    expect(saveButton.attributes('disabled')).toBeUndefined()
    await saveButton.trigger('click')
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith('aiProvider/update', {
      providerId: 1,
      values: { extra_settings: {}, api_key: 'replacement-secret' },
    })
  })

  test('requires the connection setting for a keyless provider', async () => {
    const wrapper = await testApp.mount(AIProviderFormModal, {
      props: {
        providerTypes: [
          {
            type: 'ollama',
            name: 'Ollama',
            uses_api_key: false,
            extra_fields: [
              { name: 'host', required: true, allow_blank: false },
            ],
          },
        ],
      },
    })
    await wrapper.vm.show()

    expect(wrapper.find('.actions button').attributes('disabled')).toBeDefined()

    await wrapper
      .findAll('.form-input__input')[0]
      .setValue('http://ollama:11434')
    await flushPromises()

    expect(
      wrapper.find('.actions button').attributes('disabled')
    ).toBeUndefined()
  })

  test('shows a duplicate provider type error on the provider type field', async () => {
    const dispatch = vi
      .spyOn(testApp.store, 'dispatch')
      .mockImplementation((action) => {
        if (action === 'aiProvider/create') {
          return Promise.reject({
            response: {
              data: {
                error: 'ERROR_AI_PROVIDER_TYPE_ALREADY_CONFIGURED',
                detail: 'That AI provider type is already configured.',
              },
            },
          })
        }
        return Promise.resolve()
      })
    const wrapper = await testApp.mount(AIProviderFormModal, {
      props: {
        providerTypes: [
          {
            type: 'openai',
            name: 'OpenAI',
            uses_api_key: true,
            extra_fields: [],
          },
        ],
      },
    })
    await wrapper.vm.show()
    await wrapper.find('input[type="password"]').setValue('valid-secret')
    await wrapper.find('.actions button').trigger('click')
    await flushPromises()

    const providerTypeField = wrapper
      .findAll('.control')
      .find((control) => control.find('.dropdown').exists())
    expect(providerTypeField.find('.control__messages--error').text()).toBe(
      'That AI provider type is already configured.'
    )
    expect(providerTypeField.find('.dropdown').classes()).toContain(
      'dropdown--error'
    )
    expect(dispatch).not.toHaveBeenCalledWith('toast/error', expect.anything())
  })
})
