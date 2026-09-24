import { TestApp } from '@baserow/test/helpers/testApp'
import { GenerativeAIModelType } from '@baserow/modules/core/generativeAIModelTypes'
import { getEffectiveAIAgentModels } from '@baserow/modules/integrations/ai/utils'

describe('AI Agent integration model resolution', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test.each([
    'openai',
    'anthropic',
    'google',
    'groq',
    'mistral',
    'ollama',
    'openrouter',
  ])(
    '%s inherits omitted models while preserving explicit lists',
    (providerType) => {
      const modelType = testApp
        .getRegistry()
        .get('generativeAIModel', providerType)
      const connection =
        providerType === 'ollama'
          ? { host: 'http://localhost:11434' }
          : { api_key: 'integration-key' }
      const resolve = (integrationSettings) =>
        getEffectiveAIAgentModels({
          workspaceModels: ['shared-model'],
          integrationSettings,
          modelType,
        })

      expect(resolve(connection)).toEqual(['shared-model'])
      expect(resolve({ ...connection, models: [] })).toEqual([])
      expect(resolve({ ...connection, models: ['own-model'] })).toEqual([
        'own-model',
      ])
      expect(resolve({ models: ['own-model', 'shared-model'] })).toEqual([
        'shared-model',
      ])
    }
  )

  test('does not add inherited models to an authoritative extension override', () => {
    class ExtensionModelType extends GenerativeAIModelType {
      static getType() {
        return 'extension'
      }
    }
    const modelType = new ExtensionModelType({ app: testApp.getApp() })

    expect(
      getEffectiveAIAgentModels({
        workspaceModels: ['shared-model'],
        integrationSettings: {},
        modelType,
      })
    ).toEqual([])
  })

  test('excludes a removed provider even when workspace models are stale', () => {
    expect(
      getEffectiveAIAgentModels({
        workspaceModels: ['removed-model'],
        integrationSettings: { models: ['removed-model'] },
        modelType: null,
      })
    ).toEqual([])
  })
})
