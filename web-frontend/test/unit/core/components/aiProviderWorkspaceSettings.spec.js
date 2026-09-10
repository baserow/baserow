import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import AIProviderActionsMenu from '@baserow/modules/core/components/ai/AIProviderActionsMenu'
import AIProviderFeatureSettings from '@baserow/modules/core/components/ai/AIProviderFeatureSettings'
import AIProviderWorkspaceSettings from '@baserow/modules/core/components/workspace/AIProviderWorkspaceSettings'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('AIProviderWorkspaceSettings', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
    vi.restoreAllMocks()
  })

  test('keeps legacy Kuma controls available without providers', async () => {
    const featureSetting = {
      feature_type: 'kuma',
      mode: 'inherit',
      state: 'unconfigured',
      model: null,
      inherited_model: null,
    }
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', 42)
    testApp.store.commit('aiProvider/SET_LOADED', true)
    testApp.store.commit('aiProvider/SET_PROVIDERS', [])
    testApp.store.commit('aiProvider/SET_PROVIDER_TYPES', [
      { type: 'openai', name: 'OpenAI', uses_api_key: true, extra_fields: [] },
    ])
    testApp.store.commit('aiProvider/SET_FEATURE_SETTINGS', [featureSetting])
    testApp.store.commit('settings/UPDATE_SETTINGS', {
      kuma: { is_enabled: true },
    })
    const dispatch = vi
      .spyOn(testApp.store, 'dispatch')
      .mockResolvedValue(undefined)

    vi.spyOn(
      testApp.$registry.get('aiProviderModelFeature', 'kuma'),
      'getLegacyModel'
    ).mockReturnValue('groq:legacy-model')

    const wrapper = await testApp.mount(AIProviderWorkspaceSettings, {
      props: { workspace: { id: 42 } },
    })
    await flushPromises()

    const header = wrapper.find('.ai-provider-admin__header')
    expect(header.find('button').text()).toBe('aiProviderAdmin.addProvider')
    expect(header.find('button').attributes('disabled')).toBeUndefined()
    expect(
      wrapper.find('.ai-provider-workspace-settings__toolbar').exists()
    ).toBe(false)
    const featureSettings = wrapper.findComponent(AIProviderFeatureSettings)
    expect(featureSettings.exists()).toBe(true)
    expect(featureSettings.find('.select__item').classes()).not.toContain(
      'disabled'
    )
    expect(wrapper.text()).toContain(
      'generativeAIWorkspaceSettings.noProviders'
    )

    await featureSettings.vm.updateSelection(featureSetting, 'disabled')
    expect(dispatch).toHaveBeenCalledWith('aiProvider/updateFeatureSetting', {
      featureType: 'kuma',
      values: { mode: 'disabled' },
      workspaceId: 42,
    })

    await featureSettings.vm.updateSelection(
      { ...featureSetting, mode: 'disabled', state: 'disabled' },
      'inherit'
    )
    expect(dispatch).toHaveBeenCalledWith('aiProvider/updateFeatureSetting', {
      featureType: 'kuma',
      values: { mode: 'inherit' },
      workspaceId: 42,
    })
  })

  test('keeps feature settings visible after deleting the last provider', async () => {
    const provider = {
      id: 1,
      provider_type: 'openai',
      is_active: true,
      workspace_enabled: true,
      read_only: false,
      models: [],
    }
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', 42)
    testApp.store.commit('aiProvider/SET_LOADED', true)
    testApp.store.commit('aiProvider/SET_PROVIDERS', [provider])
    testApp.store.commit('aiProvider/SET_PROVIDER_TYPES', [
      { type: 'openai', name: 'OpenAI', uses_api_key: true, extra_fields: [] },
    ])
    testApp.store.commit('aiProvider/SET_FEATURE_SETTINGS', [
      {
        feature_type: 'kuma',
        mode: 'disabled',
        state: 'disabled',
        model: null,
        inherited_model: null,
      },
    ])
    const dispatch = vi
      .spyOn(testApp.store, 'dispatch')
      .mockImplementation(async (action, payload) => {
        if (action === 'aiProvider/delete') {
          testApp.store.commit('aiProvider/DELETE_PROVIDER', payload.providerId)
        }
      })

    const wrapper = await testApp.mount(AIProviderWorkspaceSettings, {
      props: { workspace: { id: 42 } },
    })
    await wrapper.vm.runAction('provider-delete', provider)
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith('aiProvider/delete', {
      providerId: 1,
      workspaceId: 42,
    })
    expect(wrapper.findComponent(AIProviderFeatureSettings).exists()).toBe(true)
    expect(wrapper.text()).toContain(
      'generativeAIWorkspaceSettings.noProviders'
    )
  })

  test('shows inherited providers read-only and scopes their toggle', async () => {
    const inherited = {
      id: 1,
      provider_type: 'openai',
      is_active: true,
      workspace_enabled: true,
      read_only: true,
      models: [],
    }
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', 42)
    testApp.store.commit('aiProvider/SET_LOADED', true)
    testApp.store.commit('aiProvider/SET_PROVIDERS', [inherited])
    testApp.store.commit('aiProvider/SET_PROVIDER_TYPES', [
      { type: 'openai', name: 'OpenAI', uses_api_key: true, extra_fields: [] },
      {
        type: 'anthropic',
        name: 'Anthropic',
        uses_api_key: true,
        extra_fields: [],
      },
    ])
    testApp.store.commit('aiProvider/SET_FEATURE_SETTINGS', [
      {
        feature_type: 'kuma',
        mode: 'inherit',
        state: 'unconfigured',
        model: null,
        inherited_model: null,
      },
    ])
    const dispatch = vi
      .spyOn(testApp.store, 'dispatch')
      .mockResolvedValue(undefined)
    const wrapper = await testApp.mount(AIProviderWorkspaceSettings, {
      props: { workspace: { id: 42 } },
    })
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith('aiProvider/fetchInitial', {
      workspaceId: 42,
    })
    expect(wrapper.find('.ai-provider-feature-settings').exists()).toBe(true)
    expect(wrapper.text()).toContain('aiProviderAdmin.inherited')
    expect(
      wrapper
        .find('.ai-provider-admin__header')
        .find('button')
        .attributes('disabled')
    ).toBeUndefined()

    const providerActionsMenu = wrapper
      .find('.ai-provider-card__actions')
      .findComponent(AIProviderActionsMenu)
    providerActionsMenu.vm.$emit('select', 'toggle')
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith('aiProvider/update', {
      providerId: 1,
      workspaceId: 42,
      values: { is_active: false },
    })
    expect(
      dispatch.mock.calls.some(([action]) => action === 'workspace/forceUpdate')
    ).toBe(false)

    const addWorkspaceConfiguration = wrapper
      .find('.ai-provider-hierarchy__header')
      .find('button')
    await addWorkspaceConfiguration.trigger('click')
    await flushPromises()

    const providerTypeDropdown = wrapper.find('.modal__box .dropdown')
    expect(providerTypeDropdown.text()).toContain('OpenAI')
    expect(providerTypeDropdown.text()).not.toContain('Anthropic')
  })

  test('groups workspace and inherited configurations and explains model overrides', async () => {
    const inherited = {
      id: 1,
      provider_type: 'openai',
      is_active: true,
      workspace_enabled: true,
      read_only: true,
      models: [
        {
          id: 11,
          model_identifier: 'shared-model',
          is_enabled: true,
          last_test_status: null,
        },
        {
          id: 12,
          model_identifier: 'instance-model',
          is_enabled: true,
          last_test_status: null,
        },
      ],
    }
    const workspaceProvider = {
      id: 2,
      provider_type: 'openai',
      is_active: true,
      workspace_enabled: true,
      read_only: false,
      models: [
        {
          id: 21,
          model_identifier: 'shared-model',
          is_enabled: true,
          last_test_status: null,
        },
        {
          id: 22,
          model_identifier: 'workspace-model',
          is_enabled: true,
          last_test_status: null,
        },
      ],
    }
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', 42)
    testApp.store.commit('aiProvider/SET_LOADED', true)
    testApp.store.commit('aiProvider/SET_PROVIDERS', [
      inherited,
      workspaceProvider,
    ])
    testApp.store.commit('aiProvider/SET_PROVIDER_TYPES', [
      { type: 'openai', name: 'OpenAI', uses_api_key: true, extra_fields: [] },
    ])
    vi.spyOn(testApp.store, 'dispatch').mockResolvedValue(undefined)

    const wrapper = await testApp.mount(AIProviderWorkspaceSettings, {
      props: { workspace: { id: 42 } },
    })
    await flushPromises()

    expect(wrapper.findAll('.ai-provider-hierarchy')).toHaveLength(1)
    const providerLayers = wrapper.findAll('.ai-provider-card--embedded')
    expect(providerLayers).toHaveLength(2)
    expect(
      providerLayers.map((layer) =>
        layer.find('.ai-provider-card__title').text()
      )
    ).toEqual(['OpenAI', 'generativeAIWorkspaceSettings.sharedModelsTitle'])
    expect(
      providerLayers[0]
        .findAll('.ai-provider-model__name')
        .map((model) => model.text())
    ).toEqual(['shared-model', 'workspace-model'])
    expect(
      providerLayers[1]
        .findAll('.ai-provider-model__name')
        .map((model) => model.text())
    ).toEqual(['shared-model', 'instance-model'])
    expect(wrapper.text()).toContain(
      'generativeAIWorkspaceSettings.sharedModelsTitle'
    )
    expect(wrapper.findAll('.ai-provider-model--overridden')).toHaveLength(1)
    expect(wrapper.find('.ai-provider-hierarchy__description').exists()).toBe(
      false
    )
    expect(wrapper.find('.badge--green').exists()).toBe(false)
    expect(wrapper.find('.badge--purple').exists()).toBe(false)
    expect(wrapper.findAll('.ai-provider-model .badge')).toHaveLength(1)
    const overrideBadge = wrapper.find(
      '.ai-provider-model--overridden .ai-provider-model__annotation-badge'
    )
    expect(overrideBadge.classes()).toContain('badge--yellow')
    expect(overrideBadge.text()).toBe(
      'generativeAIWorkspaceSettings.overridden'
    )
    expect(overrideBadge.attributes('aria-label')).toBe(
      'generativeAIWorkspaceSettings.overriddenByWorkspace'
    )
    const overriddenMenu = wrapper
      .find('.ai-provider-model--overridden')
      .find('.ai-provider-actions-menu')
    expect(overriddenMenu.exists()).toBe(true)
    expect(overriddenMenu.find('button').attributes('disabled')).toBeDefined()
    expect(overriddenMenu.find('button').attributes('title')).toBe(
      'generativeAIWorkspaceSettings.overriddenByWorkspace'
    )
    expect(
      wrapper.findAll('.ai-provider-model__annotation-badge')
    ).toHaveLength(1)
    expect(
      wrapper
        .find('.ai-provider-admin__header')
        .find('button')
        .attributes('disabled')
    ).toBeDefined()
  })

  test('uses the provider header directly for workspace-only configurations', async () => {
    const workspaceProvider = {
      id: 2,
      provider_type: 'openai',
      is_active: true,
      workspace_enabled: true,
      read_only: false,
      models: [
        {
          id: 21,
          model_identifier: 'workspace-model',
          is_enabled: true,
          last_test_status: null,
        },
      ],
    }
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', 42)
    testApp.store.commit('aiProvider/SET_LOADED', true)
    testApp.store.commit('aiProvider/SET_PROVIDERS', [workspaceProvider])
    testApp.store.commit('aiProvider/SET_PROVIDER_TYPES', [
      { type: 'openai', name: 'OpenAI', uses_api_key: true, extra_fields: [] },
    ])
    vi.spyOn(testApp.store, 'dispatch').mockResolvedValue(undefined)

    const wrapper = await testApp.mount(AIProviderWorkspaceSettings, {
      props: { workspace: { id: 42 } },
    })
    await flushPromises()

    expect(wrapper.find('.ai-provider-hierarchy__header').exists()).toBe(false)
    expect(wrapper.findAll('.ai-provider-card--embedded')).toHaveLength(1)
    expect(wrapper.find('.ai-provider-card--primary').exists()).toBe(true)
    expect(wrapper.find('.ai-provider-card__title').text()).toBe('OpenAI')
    expect(wrapper.find('.ai-provider-card__title').element.tagName).toBe('H2')
    expect(wrapper.text()).not.toContain(
      'generativeAIWorkspaceSettings.sharedModelsTitle'
    )
  })
})
