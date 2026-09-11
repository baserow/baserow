import { flushPromises } from '@vue/test-utils'

import AIProviderActionsMenu from '@baserow/modules/core/components/ai/AIProviderActionsMenu'
import AIProviderConfirmModal from '@baserow/modules/core/components/ai/AIProviderConfirmModal'
import AdminAIProviders from '@baserow/modules/core/pages/admin/aiProviders'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('AdminAIProviders', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
    vi.restoreAllMocks()
  })

  test('keeps feature settings visible without instance providers', async () => {
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', null)
    testApp.store.commit('aiProvider/SET_LOADED', true)
    testApp.store.commit('aiProvider/SET_PROVIDERS', [])
    testApp.store.commit('aiProvider/SET_PROVIDER_TYPES', [
      { type: 'openai', name: 'OpenAI', uses_api_key: true, extra_fields: [] },
    ])
    testApp.store.commit('aiProvider/SET_FEATURE_SETTINGS', [
      {
        feature_type: 'kuma',
        mode: 'legacy',
        state: 'unconfigured',
        model: null,
        inherited_model: null,
      },
    ])
    vi.spyOn(testApp.store, 'dispatch').mockResolvedValue(undefined)

    const wrapper = await testApp.mount(AdminAIProviders)
    await flushPromises()

    const header = wrapper.find('.ai-provider-admin__header')
    expect(header.find('button').text()).toBe('aiProviderAdmin.addProvider')
    expect(wrapper.find('.ai-provider-feature-settings').exists()).toBe(true)
    expect(wrapper.text()).toContain('aiProviderAdmin.noProviders')
  })

  test('shows the skeleton while the providers are being fetched', async () => {
    vi.spyOn(testApp.store, 'dispatch').mockReturnValue(new Promise(() => {}))

    const wrapper = await testApp.mount(AdminAIProviders)
    await flushPromises()

    expect(wrapper.find('.skeleton').exists()).toBe(true)
    expect(wrapper.findAll('.ai-provider-card').length).toBeGreaterThan(0)
    expect(wrapper.find('.loading').exists()).toBe(false)
  })

  test('shows a recoverable error instead of an endless initial spinner', async () => {
    let fetchAttempt = 0
    const dispatch = vi
      .spyOn(testApp.store, 'dispatch')
      .mockImplementation((action) => {
        if (action === 'aiProvider/fetchInitial') {
          fetchAttempt += 1
          return fetchAttempt === 1
            ? Promise.reject(new Error('Unavailable'))
            : Promise.resolve()
        }
        return Promise.resolve()
      })
    const wrapper = await testApp.mount(AdminAIProviders)
    await flushPromises()

    expect(wrapper.text()).toContain('aiProviderAdmin.loadError')
    expect(wrapper.find('.skeleton').exists()).toBe(false)

    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'aiProviderAdmin.retry')
      .trigger('click')
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith('aiProvider/fetchInitial')
    expect(fetchAttempt).toBe(2)
    expect(wrapper.text()).not.toContain('aiProviderAdmin.loadErrorDescription')
  })

  test('renders the instance scope it loaded, not another scope', async () => {
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', null)
    testApp.store.commit('aiProvider/SET_LOADED', true)
    testApp.store.commit('aiProvider/SET_PROVIDERS', [
      {
        id: 1,
        provider_type: 'openai',
        is_active: true,
        extra_settings: {},
        models: [
          {
            id: 2,
            model_identifier: 'gpt-5.6',
            is_enabled: true,
            last_test_status: null,
          },
        ],
      },
    ])
    testApp.store.commit('aiProvider/SET_PROVIDER_TYPES', [
      { type: 'openai', name: 'OpenAI', uses_api_key: true, extra_fields: [] },
    ])
    vi.spyOn(testApp.store, 'dispatch').mockResolvedValue(undefined)

    const wrapper = await testApp.mount(AdminAIProviders)
    await flushPromises()

    expect(wrapper.find('.ai-provider-model__name').text()).toBe('gpt-5.6')

    // A workspace-scoped store must not paint the instance admin page.
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', 42)
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).not.toContain('gpt-5.6')
    expect(wrapper.find('.skeleton').exists()).toBe(true)
  })

  const mountWithModel = async (model, usage) => {
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', null)
    testApp.store.commit('aiProvider/SET_LOADED', true)
    testApp.store.commit('aiProvider/SET_PROVIDERS', [
      {
        id: 1,
        provider_type: 'openai',
        is_active: true,
        extra_settings: {},
        models: [model],
      },
    ])
    testApp.store.commit('aiProvider/SET_PROVIDER_TYPES', [
      { type: 'openai', name: 'OpenAI', uses_api_key: true, extra_fields: [] },
    ])
    const dispatch = vi
      .spyOn(testApp.store, 'dispatch')
      .mockImplementation(async (action) => {
        if (action === 'aiProvider/fetchModelUsage') {
          return usage
        }
      })
    const wrapper = await testApp.mount(AdminAIProviders)
    await flushPromises()
    return { wrapper, dispatch }
  }

  const selectModelAction = async (wrapper, action) => {
    wrapper
      .find('.ai-provider-model__actions')
      .findComponent(AIProviderActionsMenu)
      .vm.$emit('select', action)
    await flushPromises()
  }

  test('warns with the instance-wide usage counts before disabling a model', async () => {
    const { wrapper, dispatch } = await mountWithModel(
      {
        id: 2,
        model_identifier: 'gpt-5.6',
        is_enabled: true,
        last_test_status: null,
      },
      {
        usage: [{ featureType: 'ai_fields', count: 3 }],
        blockingFeatureTypes: [],
      }
    )

    await selectModelAction(wrapper, 'toggle')

    expect(dispatch).toHaveBeenCalledWith('aiProvider/fetchModelUsage', {
      modelId: 2,
    })
    const confirmModal = wrapper.findComponent(AIProviderConfirmModal)
    expect(confirmModal.props('title')).toBe(
      'aiProviderAdmin.disableModelTitle'
    )
    expect(confirmModal.props('message')).toMatch(
      /^aiProviderAdmin\.modelInUse.* aiProviderAdmin\.disableModelDescription$/
    )

    confirmModal.vm.$emit('confirm')
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith('aiProvider/updateModel', {
      modelId: 2,
      values: { is_enabled: false },
    })
  })

  test('disables a model nothing depends on without a confirmation', async () => {
    const { wrapper, dispatch } = await mountWithModel(
      {
        id: 2,
        model_identifier: 'gpt-5.6',
        is_enabled: true,
        last_test_status: null,
      },
      {
        usage: [{ featureType: 'ai_fields', count: 0 }],
        blockingFeatureTypes: [],
      }
    )

    await selectModelAction(wrapper, 'toggle')

    expect(wrapper.findComponent(AIProviderConfirmModal).exists()).toBe(false)
    expect(dispatch).toHaveBeenCalledWith('aiProvider/updateModel', {
      modelId: 2,
      values: { is_enabled: false },
    })
  })

  test('tests every provider model in one request', async () => {
    let finishRequest
    const dispatch = vi.fn(
      () =>
        new Promise((resolve) => {
          finishRequest = resolve
        })
    )
    const showActionError = vi.fn()
    const provider = { models: [{ id: 1 }, { id: 2 }] }
    const context = {
      $store: { dispatch },
      showActionError,
      testingModelIds: [],
    }

    const result = AdminAIProviders.methods.runAction.call(
      context,
      'provider-models-test',
      provider
    )

    expect(context.testingModelIds).toEqual([1, 2])
    finishRequest([])
    const succeeded = await result

    expect(dispatch).toHaveBeenCalledOnce()
    expect(dispatch).toHaveBeenCalledWith('aiProvider/testModels', {
      model_ids: [1, 2],
    })
    expect(showActionError).not.toHaveBeenCalled()
    expect(succeeded).toBe(true)
    expect(context.testingModelIds).toEqual([])
  })

  test('runs a single model test without opening a confirmation', async () => {
    const runAction = vi.fn().mockResolvedValue(true)
    const model = { id: 1 }
    const context = { runAction }

    const result = await AdminAIProviders.methods.testModel.call(context, model)

    expect(runAction).toHaveBeenCalledWith('model-test', model)
    expect(result).toBe(true)
  })
})
