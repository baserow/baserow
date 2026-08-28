import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
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
