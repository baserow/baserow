import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import AIProviderFeatureSettings from '@baserow/modules/core/components/ai/AIProviderFeatureSettings'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('AIProviderFeatureSettings', () => {
  let testApp = null

  const translate = (key, values = {}) => {
    if (key === 'aiProviderAdmin.kumaUseLegacy') {
      return `Use legacy environment model: ${values.model}`
    }
    if (key === 'aiProviderAdmin.kumaLegacyFallback') {
      return `legacy environment model: ${values.model}`
    }
    if (key === 'aiProviderAdmin.kumaLegacyEmpty') {
      return 'empty'
    }
    if (key === 'aiProviderAdmin.kumaInvalidFallback') {
      return `Selected model unavailable — using legacy environment model: ${values.model}`
    }
    if (key === 'aiProviderAdmin.kumaInvalidNoFallback') {
      return 'Selected model unavailable — no legacy environment model configured'
    }
    if (key === 'aiProviderAdmin.kumaUseInstance') {
      return `Use instance setting — ${values.model}`
    }
    if (key === 'aiProviderAdmin.kumaDisabled') {
      return 'Disabled'
    }
    if (key === 'aiProviderAdmin.kumaInheritedUnavailable') {
      return 'selected model unavailable in this workspace'
    }
    if (key === 'aiProviderAdmin.modelScopeInstance') {
      return 'Instance'
    }
    if (key === 'aiProviderAdmin.modelScopeWorkspace') {
      return 'Workspace'
    }
    return key
  }

  const mountComponent = (legacyModel = '', props = {}) => {
    // The component asks the feature type for its environment model, so the
    // registered Kuma type is what has to report the value under test.
    vi.spyOn(
      testApp.$registry.get('aiProviderModelFeature', 'kuma'),
      'getLegacyModel'
    ).mockReturnValue(legacyModel)
    return testApp.mount(AIProviderFeatureSettings, {
      props,
      global: { mocks: { $t: translate } },
    })
  }

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
    vi.restoreAllMocks()
  })

  test('only offers models made available to Kuma and saves one selection', async () => {
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', null)
    testApp.store.commit('aiProvider/SET_PROVIDER_TYPES', [
      { type: 'openai', name: 'OpenAI' },
    ])
    testApp.store.commit('aiProvider/SET_PROVIDERS', [
      {
        id: 1,
        provider_type: 'openai',
        is_active: true,
        models: [
          {
            id: 2,
            model_identifier: 'shared-model',
            is_enabled: true,
            feature_types: ['ai_fields', 'kuma'],
          },
          {
            id: 3,
            model_identifier: 'kuma-only-model',
            is_enabled: true,
            feature_types: ['kuma'],
          },
          {
            id: 4,
            model_identifier: 'ai-field-only-model',
            is_enabled: true,
            feature_types: ['ai_fields'],
          },
        ],
      },
    ])
    const setting = {
      feature_type: 'kuma',
      mode: 'disabled',
      state: 'disabled',
      model: null,
      inherited_model: null,
    }
    testApp.store.commit('aiProvider/SET_FEATURE_SETTINGS', [setting])
    const dispatch = vi
      .spyOn(testApp.store, 'dispatch')
      .mockResolvedValue({ ...setting, mode: 'model' })

    const wrapper = await testApp.mount(AIProviderFeatureSettings)

    expect(wrapper.vm.modelGroups('kuma')).toEqual([
      {
        id: 1,
        name: 'OpenAI',
        models: [
          { id: 2, name: 'shared-model' },
          { id: 3, name: 'kuma-only-model' },
        ],
      },
    ])

    await wrapper.vm.updateSelection(setting, 'model:3')

    expect(dispatch).toHaveBeenCalledWith('aiProvider/updateFeatureSetting', {
      featureType: 'kuma',
      values: { mode: 'model', model_id: 3 },
      workspaceId: null,
    })
    expect(wrapper.emitted('updated')).toBeUndefined()
    expect(wrapper.find('.dropdown').attributes('aria-label')).toBeTruthy()
  })

  test('distinguishes workspace and instance models with the same identifier', async () => {
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', 42)
    testApp.store.commit('aiProvider/SET_PROVIDER_TYPES', [
      { type: 'openai', name: 'OpenAI' },
    ])
    testApp.store.commit('aiProvider/SET_PROVIDERS', [
      {
        id: 1,
        provider_type: 'openai',
        is_active: true,
        read_only: false,
        models: [
          {
            id: 10,
            model_identifier: 'gpt-5.6',
            is_enabled: true,
            feature_types: ['kuma'],
          },
        ],
      },
      {
        id: 2,
        provider_type: 'openai',
        is_active: true,
        read_only: true,
        models: [
          {
            id: 20,
            model_identifier: 'gpt-5.6',
            is_enabled: true,
            feature_types: ['kuma'],
          },
        ],
      },
    ])
    testApp.store.commit('aiProvider/SET_FEATURE_SETTINGS', [
      {
        feature_type: 'kuma',
        mode: 'model',
        state: 'overridden',
        model: { id: 20 },
        inherited_model: null,
      },
    ])

    const wrapper = await mountComponent('', { workspaceId: 42 })

    const dropdown = wrapper.find('.dropdown')
    expect(dropdown.find('.dropdown__selected-text').text()).toBe(
      'OpenAI · Instance · gpt-5.6'
    )

    await dropdown.find('.dropdown__selected').trigger('click')
    const modelRows = dropdown.findAll('.dropdown-section .select__item')
    expect(
      modelRows.map((row) => row.find('.select__item-name-text').text())
    ).toEqual(['gpt-5.6', 'gpt-5.6'])

    const search = dropdown.find('.select__search-input')
    await search.setValue('Instance')
    await search.trigger('keyup')

    expect(modelRows[0].classes()).toContain('hidden')
    expect(modelRows[1].classes()).toContain('visible')

    testApp.store.commit('aiProvider/UPDATE_MODEL', {
      id: 20,
      model_identifier: 'gpt-5.7',
      is_enabled: true,
      feature_types: ['kuma'],
    })
    await wrapper.vm.$nextTick()

    expect(dropdown.find('.dropdown__selected-text').text()).toBe(
      'OpenAI · Instance · gpt-5.7'
    )
  })

  test('keeps each dropdown disabled until its own save resolves', async () => {
    const settings = ['kuma', 'ai_fields'].map((featureType) => ({
      feature_type: featureType,
      mode: 'disabled',
      state: 'disabled',
      model: null,
      inherited_model: null,
    }))
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', null)
    testApp.store.commit('aiProvider/SET_FEATURE_SETTINGS', settings)
    const resolvers = {}
    vi.spyOn(testApp.store, 'dispatch').mockImplementation(
      (action, payload) =>
        new Promise((resolve) => {
          resolvers[payload.featureType] = resolve
        })
    )

    const wrapper = await mountComponent()
    const first = wrapper.vm.updateSelection(settings[0], 'legacy')
    const second = wrapper.vm.updateSelection(settings[1], 'legacy')

    expect(wrapper.vm.savingFeatures).toEqual(['kuma', 'ai_fields'])

    resolvers.ai_fields()
    await second
    // The slower save must still hold its own dropdown disabled.
    expect(wrapper.vm.savingFeatures).toEqual(['kuma'])

    resolvers.kuma()
    await first
    expect(wrapper.vm.savingFeatures).toEqual([])
  })

  test('shows and enables the configured legacy environment model', async () => {
    const setting = {
      feature_type: 'kuma',
      mode: 'disabled',
      state: 'disabled',
      model: null,
      inherited_model: null,
    }
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', null)
    testApp.store.commit('aiProvider/SET_FEATURE_SETTINGS', [setting])
    const dispatch = vi.spyOn(testApp.store, 'dispatch').mockResolvedValue({
      ...setting,
      mode: 'legacy',
      state: 'unconfigured',
    })

    const wrapper = await mountComponent('groq:legacy-model')
    const legacyOption = wrapper.find('.select__item')

    expect(legacyOption.text()).toBe(
      'Use legacy environment model: groq:legacy-model'
    )
    expect(legacyOption.classes()).not.toContain('disabled')

    await legacyOption.find('.select__item-link').trigger('click')
    expect(dispatch).toHaveBeenCalledWith('aiProvider/updateFeatureSetting', {
      featureType: 'kuma',
      values: { mode: 'legacy' },
      workspaceId: null,
    })
  })

  test('shows an empty legacy environment model and disables it', async () => {
    const setting = {
      feature_type: 'kuma',
      mode: 'legacy',
      state: 'unconfigured',
      model: null,
      inherited_model: null,
    }
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', null)
    testApp.store.commit('aiProvider/SET_FEATURE_SETTINGS', [setting])
    const dispatch = vi.spyOn(testApp.store, 'dispatch')

    const wrapper = await mountComponent()
    const legacyOption = wrapper.find('.select__item')

    expect(wrapper.find('.dropdown__selected-text').text()).toBe(
      'Use legacy environment model: empty'
    )
    expect(legacyOption.text()).toBe('Use legacy environment model: empty')
    expect(legacyOption.classes()).toContain('disabled')
    expect(wrapper.findAll('.select__item')[1].classes()).not.toContain(
      'disabled'
    )

    await legacyOption.find('.select__item-link').trigger('click')
    expect(dispatch).not.toHaveBeenCalledWith(
      'aiProvider/updateFeatureSetting',
      expect.anything()
    )
  })

  test('shows the legacy environment model for an invalid selection', async () => {
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', null)
    testApp.store.commit('aiProvider/SET_FEATURE_SETTINGS', [
      {
        feature_type: 'kuma',
        mode: 'model',
        state: 'invalid',
        model: null,
        inherited_model: null,
      },
    ])

    const wrapper = await mountComponent('groq:legacy-model')
    const invalidOption = wrapper.find('.select__item')

    expect(invalidOption.text()).toBe(
      'Selected model unavailable — using legacy environment model: groq:legacy-model'
    )
    expect(invalidOption.classes()).toContain('disabled')
  })

  test('shows that an invalid selection has no legacy environment model', async () => {
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', null)
    testApp.store.commit('aiProvider/SET_FEATURE_SETTINGS', [
      {
        feature_type: 'kuma',
        mode: 'model',
        state: 'invalid',
        model: null,
        inherited_model: null,
      },
    ])

    const wrapper = await mountComponent()
    const invalidOption = wrapper.find('.select__item')

    expect(invalidOption.text()).toBe(
      'Selected model unavailable — no legacy environment model configured'
    )
    expect(invalidOption.classes()).toContain('disabled')
  })

  test('shows and enables the configured legacy model in a workspace', async () => {
    const setting = {
      feature_type: 'kuma',
      mode: 'disabled',
      state: 'disabled',
      model: null,
      inherited_model: null,
    }
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', 42)
    testApp.store.commit('aiProvider/SET_FEATURE_SETTINGS', [setting])
    testApp.store.commit('settings/UPDATE_SETTINGS', {
      kuma: { is_enabled: true },
    })

    const wrapper = await mountComponent('groq:legacy-model', {
      workspaceId: 42,
    })
    const inheritOption = wrapper.find('.select__item')

    expect(inheritOption.text()).toBe(
      'Use instance setting — legacy environment model: groq:legacy-model'
    )
    expect(inheritOption.classes()).not.toContain('disabled')
  })

  test('disables an empty legacy model in a workspace', async () => {
    const setting = {
      feature_type: 'kuma',
      mode: 'disabled',
      state: 'disabled',
      model: null,
      inherited_model: null,
    }
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', 42)
    testApp.store.commit('aiProvider/SET_FEATURE_SETTINGS', [setting])

    const wrapper = await mountComponent('', { workspaceId: 42 })
    const inheritOption = wrapper.find('.select__item')

    expect(inheritOption.text()).toBe(
      'Use instance setting — legacy environment model: empty'
    )
    expect(inheritOption.classes()).toContain('disabled')
  })

  test('labels an explicitly disabled instance setting in a workspace', async () => {
    const setting = {
      feature_type: 'kuma',
      mode: 'model',
      state: 'overridden',
      model: { id: 30 },
      inherited_model: null,
      inherited_state: 'disabled',
    }
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', 42)
    testApp.store.commit('aiProvider/SET_FEATURE_SETTINGS', [setting])

    const wrapper = await mountComponent('groq:legacy-model', {
      workspaceId: 42,
    })
    const inheritOption = wrapper.find('.select__item')

    expect(inheritOption.text()).toBe('Use instance setting — Disabled')
    expect(inheritOption.classes()).not.toContain('disabled')
  })

  test('allows inheriting an explicitly disabled instance without a legacy model', async () => {
    const setting = {
      feature_type: 'kuma',
      mode: 'model',
      state: 'overridden',
      model: { id: 30 },
      inherited_model: null,
      inherited_state: 'disabled',
    }
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', 42)
    testApp.store.commit('aiProvider/SET_FEATURE_SETTINGS', [setting])

    const wrapper = await mountComponent('', { workspaceId: 42 })
    const inheritOption = wrapper.find('.select__item')

    expect(inheritOption.text()).toBe('Use instance setting — Disabled')
    expect(inheritOption.classes()).not.toContain('disabled')
  })

  test('falls back to the instance flag when the backend omits inherited_state', async () => {
    const setting = {
      feature_type: 'kuma',
      mode: 'model',
      state: 'overridden',
      model: { id: 30 },
      inherited_model: null,
    }
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', 42)
    testApp.store.commit('aiProvider/SET_FEATURE_SETTINGS', [setting])
    testApp.store.commit('settings/UPDATE_SETTINGS', {
      kuma: { is_enabled: false },
    })

    const wrapper = await mountComponent('groq:legacy-model', {
      workspaceId: 42,
    })

    expect(wrapper.find('.select__item').text()).toBe(
      'Use instance setting — Disabled'
    )
  })

  test('never presents an unresolvable instance selection as the legacy model', async () => {
    const setting = {
      feature_type: 'kuma',
      mode: 'disabled',
      state: 'disabled',
      model: null,
      inherited_model: null,
      inherited_state: 'invalid',
    }
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', 42)
    testApp.store.commit('aiProvider/SET_FEATURE_SETTINGS', [setting])
    testApp.store.commit('settings/UPDATE_SETTINGS', {
      kuma: { is_enabled: true },
    })

    const wrapper = await mountComponent('groq:legacy-model', {
      workspaceId: 42,
    })
    const inheritOption = wrapper.find('.select__item')

    expect(inheritOption.text()).toBe(
      'Use instance setting — selected model unavailable in this workspace'
    )
    expect(inheritOption.classes()).toContain('disabled')
  })

  test('keeps a database-backed instance model enabled without a legacy model', async () => {
    const setting = {
      feature_type: 'kuma',
      mode: 'disabled',
      state: 'disabled',
      model: null,
      inherited_model: {
        id: 20,
        provider_type: 'openai',
        model_identifier: 'gpt-5.6',
      },
    }
    testApp.store.commit('aiProvider/SET_WORKSPACE_ID', 42)
    testApp.store.commit('aiProvider/SET_PROVIDER_TYPES', [
      { type: 'openai', name: 'OpenAI' },
    ])
    testApp.store.commit('aiProvider/SET_PROVIDERS', [
      {
        id: 2,
        provider_type: 'openai',
        is_active: true,
        read_only: true,
        models: [],
      },
    ])
    testApp.store.commit('aiProvider/SET_FEATURE_SETTINGS', [setting])

    const wrapper = await mountComponent('', { workspaceId: 42 })
    const inheritOption = wrapper.find('.select__item')

    expect(inheritOption.text()).toBe('Use instance setting — OpenAI · gpt-5.6')
    expect(inheritOption.classes()).not.toContain('disabled')
  })
})
