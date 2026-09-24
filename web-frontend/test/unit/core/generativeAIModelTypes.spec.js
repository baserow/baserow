import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import { GenerativeAIModelType } from '@baserow/modules/core/generativeAIModelTypes'
import GenerativeAIWorkspaceSettings from '@baserow/modules/core/components/workspace/GenerativeAIWorkspaceSettings'

describe('Generative AI model types', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('registers Google and Groq in the provider registry', () => {
    const registry = testApp.getRegistry()

    expect(
      registry
        .getOrderedList('generativeAIModel')
        .map((modelType) => modelType.getType())
    ).toEqual([
      'openai',
      'anthropic',
      'google',
      'groq',
      'mistral',
      'ollama',
      'openrouter',
    ])
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

  test('keeps database-only providers out of legacy workspace settings', () => {
    const registry = testApp.getRegistry()

    const legacyModelTypes =
      GenerativeAIWorkspaceSettings.computed.modelTypes.call({
        $registry: registry,
      })

    expect(legacyModelTypes.map(([type]) => type)).toEqual([
      'openai',
      'anthropic',
      'mistral',
      'ollama',
      'openrouter',
    ])
    expect(registry.exists('generativeAIModel', 'google')).toBe(true)
    expect(registry.exists('generativeAIModel', 'groq')).toBe(true)
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
    },
    {
      providerType: 'groq',
      name: 'generativeAIModelType.groq',
      canPromptWithFiles: false,
    },
  ])(
    'provides form metadata for $providerType',
    ({ providerType, name, canPromptWithFiles }) => {
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
      expect(modelType.canPromptWithFiles()).toBe(canPromptWithFiles)
    }
  )
})
