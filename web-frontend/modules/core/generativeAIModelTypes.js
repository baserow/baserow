import { Registerable } from '@baserow/modules/core/registry'
import { url, helpers } from '@vuelidate/validators'

export class GenerativeAIModelType extends Registerable {
  get name() {
    throw new Error('Must be set on the type.')
  }

  /**
   * Indicates whether files can be used as a knowledge base
   * for the prompt.
   */
  canPromptWithFiles() {
    return false
  }

  getOrder() {
    return 50
  }

  getMaxTemperature() {
    return 2
  }
}

const modelSettings = (label, description) => ({
  key: 'models',
  label,
  description,
  serialize: (value) => {
    return value
      .split(',')
      .map((model) => model.trim())
      .filter((model) => model !== '')
  },
  parse: (value) => {
    return Array.isArray(value) ? value.join(', ') : value
  },
})

export class OpenAIModelType extends GenerativeAIModelType {
  static getType() {
    return 'openai'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('generativeAIModelType.openai')
  }

  getSettings() {
    const { i18n } = this.app
    return [
      {
        key: 'api_key',
        label: i18n.t('generativeAIModelType.openaiApiKeyLabel'),
        description: i18n.t('generativeAIModelType.openaiApiKeyDescription'),
      },
      {
        key: 'organization',
        label: i18n.t('generativeAIModelType.openaiOrganization'),
        optional: true,
      },
      {
        key: 'base_url',
        label: i18n.t('generativeAIModelType.openaiBaseUrl'),
        description: i18n.t('generativeAIModelType.openaiBaseUrlDescription'),
        validations: {
          url: helpers.withMessage(this.app.i18n.t('error.invalidURL'), url),
        },
      },
      modelSettings(
        i18n.t('generativeAIModelType.openaiModelsLabel'),
        i18n.t('generativeAIModelType.openaiModelsDescription')
      ),
    ]
  }

  canPromptWithFiles() {
    return true
  }

  getOrder() {
    return 10
  }
}

export class AnthropicModelType extends GenerativeAIModelType {
  static getType() {
    return 'anthropic'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('generativeAIModelType.anthropic')
  }

  getSettings() {
    const { i18n } = this.app
    return [
      {
        key: 'api_key',
        label: i18n.t('generativeAIModelType.anthropicApiKeyLabel'),
        description: i18n.t('generativeAIModelType.anthropicApiKeyDescription'),
      },
      modelSettings(
        i18n.t('generativeAIModelType.anthropicModelsLabel'),
        i18n.t('generativeAIModelType.anthropicModelsDescription')
      ),
    ]
  }

  getOrder() {
    return 20
  }

  getMaxTemperature() {
    return 1
  }
}

export class MistralModelType extends GenerativeAIModelType {
  static getType() {
    return 'mistral'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('generativeAIModelType.mistral')
  }

  getSettings() {
    const { i18n } = this.app
    return [
      {
        key: 'api_key',
        label: i18n.t('generativeAIModelType.mistralApiKeyLabel'),
        description: i18n.t('generativeAIModelType.mistralApiKeyDescription'),
      },
      modelSettings(
        i18n.t('generativeAIModelType.mistralModelsLabel'),
        i18n.t('generativeAIModelType.mistralModelsDescription')
      ),
    ]
  }

  getOrder() {
    return 30
  }

  getMaxTemperature() {
    return 1
  }
}

export class OllamaModelType extends GenerativeAIModelType {
  static getType() {
    return 'ollama'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('generativeAIModelType.ollama')
  }

  getSettings() {
    const { i18n } = this.app
    return [
      {
        key: 'host',
        label: i18n.t('generativeAIModelType.ollamaHostLabel'),
        description: i18n.t('generativeAIModelType.ollamaHostDescription'),
      },
      modelSettings(
        i18n.t('generativeAIModelType.ollamaModelsLabel'),
        i18n.t('generativeAIModelType.ollamaModelsDescription')
      ),
    ]
  }

  getOrder() {
    return 40
  }

  getMaxTemperature() {
    return 1
  }
}

export class OpenRouterModelType extends GenerativeAIModelType {
  static getType() {
    return 'openrouter'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('generativeAIModelType.openRouter')
  }

  getSettings() {
    const { i18n } = this.app
    return [
      {
        key: 'api_key',
        label: i18n.t('generativeAIModelType.openRouterApiKeyLabel'),
        description: i18n.t(
          'generativeAIModelType.openRouterApiKeyDescription'
        ),
      },
      {
        key: 'organization',
        label: i18n.t('generativeAIModelType.openRouterOrganization'),
        optional: true,
      },
      modelSettings(
        i18n.t('generativeAIModelType.openRouterModelsLabel'),
        i18n.t('generativeAIModelType.openRouterModelsDescription')
      ),
    ]
  }

  getOrder() {
    return 50
  }
}
