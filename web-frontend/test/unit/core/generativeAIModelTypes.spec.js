import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import { GenerativeAIModelType } from '@baserow/modules/core/generativeAIModelTypes'

describe('Generative AI model types', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('registers the built-in providers in order', () => {
    const registry = testApp.getRegistry()

    expect(
      registry
        .getOrderedList('generativeAIModel')
        .map((modelType) => modelType.getType())
    ).toEqual([
      'openai',
      'anthropic',
      'bedrock',
      'google',
      'groq',
      'xai',
      'zai',
      'mistral',
      'ollama',
      'openrouter',
    ])
  })

  test('describes the Bedrock connection and its secret', () => {
    const bedrock = testApp.getRegistry().get('generativeAIModel', 'bedrock')

    expect(bedrock.getSettings().map((setting) => setting.key)).toEqual([
      'api_key',
      'access_key_id',
      'region',
      'models',
    ])
    expect(bedrock.getSetting('access_key_id').optional).toBe(true)
    expect(bedrock.getRequiredIntegrationSettings()).toEqual([
      'api_key',
      'region',
    ])
    expect(bedrock.isIntegrationSettingsComplete({ api_key: 'secret' })).toBe(
      false
    )
    expect(
      bedrock.isIntegrationSettingsComplete({
        api_key: 'secret',
        region: 'eu-central-1',
      })
    ).toBe(true)
    expect(bedrock.canPromptWithFiles()).toBe(true)
    expect(bedrock.getMaxTemperature()).toBe(1)
    expect(bedrock.getSecretFieldText()).toEqual({
      label: 'generativeAIModelType.bedrockSecretLabel',
      change: 'generativeAIModelType.bedrockChangeSecret',
      updateHint: 'generativeAIModelType.bedrockSecretUpdateHint',
    })
  })

  test('keeps the generic API key wording for other providers', () => {
    const openai = testApp.getRegistry().get('generativeAIModel', 'openai')

    expect(openai.getSecretFieldText()).toEqual({
      label: 'aiProviderAdmin.apiKey',
      change: 'aiProviderAdmin.changeApiKey',
      updateHint: 'aiProviderAdmin.apiKeyUpdateHint',
    })
  })

  test('marks every registered provider as a built-in provider type', () => {
    const modelTypes = testApp.getRegistry().getOrderedList('generativeAIModel')

    expect(
      modelTypes
        .filter((modelType) => !modelType.isBuiltInProviderType())
        .map((modelType) => modelType.getType())
    ).toEqual([])
  })

  test('does not treat a plugin provider as a built-in provider type', () => {
    class ExtensionModelType extends GenerativeAIModelType {
      static getType() {
        return 'extension'
      }
    }

    expect(
      new ExtensionModelType({ app: testApp.getApp() }).isBuiltInProviderType()
    ).toBe(false)
  })

  test('only treats self-contained integration connections as complete', () => {
    const registry = testApp.getRegistry()
    const openai = registry.get('generativeAIModel', 'openai')
    const ollama = registry.get('generativeAIModel', 'ollama')

    expect(
      openai.isIntegrationSettingsComplete({
        base_url: 'https://example.com/v1',
        models: ['model'],
      })
    ).toBe(false)
    expect(
      openai.isIntegrationSettingsComplete({
        api_key: 'secret',
        models: ['model'],
      })
    ).toBe(true)
    expect(ollama.isIntegrationSettingsComplete({ models: ['model'] })).toBe(
      false
    )
    expect(
      ollama.isIntegrationSettingsComplete({
        host: 'http://localhost:11434',
        models: ['model'],
      })
    ).toBe(true)
  })

  test.each([
    {
      providerType: 'google',
      name: 'generativeAIModelType.google',
      canPromptWithFiles: true,
      maxTemperature: 2,
    },
    {
      providerType: 'groq',
      name: 'generativeAIModelType.groq',
      canPromptWithFiles: false,
      maxTemperature: 2,
    },
    {
      providerType: 'xai',
      name: 'generativeAIModelType.xai',
      canPromptWithFiles: true,
      maxTemperature: 2,
    },
    {
      providerType: 'zai',
      name: 'generativeAIModelType.zai',
      canPromptWithFiles: true,
      maxTemperature: 1,
    },
  ])(
    'provides form metadata for $providerType',
    ({ providerType, name, canPromptWithFiles, maxTemperature }) => {
      const modelType = testApp
        .getRegistry()
        .get('generativeAIModel', providerType)

      expect(modelType.getName()).toBe(name)
      expect(modelType.getSettings()).toEqual([
        {
          key: 'api_key',
          label: `generativeAIModelType.${providerType}ApiKeyLabel`,
          description: `generativeAIModelType.${providerType}ApiKeyDescription`,
        },
        {
          key: 'models',
          label: `generativeAIModelType.${providerType}ModelsLabel`,
          description: `generativeAIModelType.${providerType}ModelsDescription`,
          serialize: expect.any(Function),
          parse: expect.any(Function),
        },
      ])
      expect(modelType.getModelIdentifierDescription()).toBe(
        `generativeAIModelType.${providerType}ModelIdentifierDescription`
      )
      expect(modelType.getRequiredIntegrationSettings()).toEqual(['api_key'])
      expect(modelType.canPromptWithFiles()).toBe(canPromptWithFiles)
      expect(modelType.getMaxTemperature()).toBe(maxTemperature)
    }
  )
})
