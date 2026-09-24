import { getEnabledModelsForAIProviderFeature } from '@baserow/modules/core/aiProviderModelFeatureTypes'

describe('getEnabledModelsForAIProviderFeature', () => {
  test('uses the feature-filtered models when the backend provides them', () => {
    const workspace = {
      generative_ai_models_enabled: {
        openai: ['ai-fields-model', 'kuma-only'],
      },
      ai_features: {
        ai_fields: {
          models: { openai: ['ai-fields-model'] },
        },
      },
    }

    expect(
      getEnabledModelsForAIProviderFeature(workspace, 'ai_fields')
    ).toEqual({ openai: ['ai-fields-model'] })
  })

  test('falls back to the generic models during a rolling upgrade', () => {
    const workspace = {
      generative_ai_models_enabled: { openai: ['legacy-model'] },
    }

    expect(
      getEnabledModelsForAIProviderFeature(workspace, 'ai_fields')
    ).toEqual({ openai: ['legacy-model'] })
  })

  test('uses live legacy models while feature filtering is disabled', () => {
    const workspace = {
      generative_ai_models_enabled: { openai: ['updated-legacy-model'] },
      ai_features: {
        ai_fields: { models: { openai: ['stale-model'] } },
      },
    }

    expect(
      getEnabledModelsForAIProviderFeature(workspace, 'ai_fields', false)
    ).toEqual({ openai: ['updated-legacy-model'] })
  })
})
