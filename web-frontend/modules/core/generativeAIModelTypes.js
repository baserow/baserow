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

  /**
   * Returns whether this provider can be configured through legacy workspace
   * settings. Database-backed provider forms do not use this value.
   *
   * @returns {boolean} Whether legacy workspace settings support this provider.
   */
  supportsLegacyWorkspaceSettings() {
    return true
  }

  /**
   * Returns an array of objects that define the settings for workspace
   * Generative AI and integration overrides. The array can be empty if
   * the model type is not configurable.
   *
   * Each setting object in the array describes a form field. See
   * `modelSettings` for a full example. A setting may only define
   * a subset of the properties.
   *
   * @returns {Array<Object>} An array of setting objects. Can be empty.
   */
  getSettings() {
    return []
  }

  getSetting(key) {
    return this.getSettings().find((setting) => setting.key === key) || null
  }

  getModelIdentifierDescription() {
    return null
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
    const { $i18n: i18n } = this.app
    return i18n.t('generativeAIModelType.openai')
  }

  getSettings() {
    const { $i18n: i18n } = this.app
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
          url: helpers.withMessage(this.app.$i18n.t('error.invalidURL'), url),
        },
      },
      modelSettings(
        i18n.t('generativeAIModelType.openaiModelsLabel'),
        i18n.t('generativeAIModelType.openaiModelsDescription')
      ),
    ]
  }

  getModelIdentifierDescription() {
    return this.app.$i18n.t(
      'generativeAIModelType.openaiModelIdentifierDescription'
    )
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
    const { $i18n: i18n } = this.app
    return i18n.t('generativeAIModelType.anthropic')
  }

  getSettings() {
    const { $i18n: i18n } = this.app
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

  getModelIdentifierDescription() {
    return this.app.$i18n.t(
      'generativeAIModelType.anthropicModelIdentifierDescription'
    )
  }

  getOrder() {
    return 20
  }

  canPromptWithFiles() {
    return true
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
    const { $i18n: i18n } = this.app
    return i18n.t('generativeAIModelType.mistral')
  }

  getSettings() {
    const { $i18n: i18n } = this.app
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

  getModelIdentifierDescription() {
    return this.app.$i18n.t(
      'generativeAIModelType.mistralModelIdentifierDescription'
    )
  }

  getOrder() {
    return 50
  }

  canPromptWithFiles() {
    return true
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
    const { $i18n: i18n } = this.app
    return i18n.t('generativeAIModelType.ollama')
  }

  getSettings() {
    const { $i18n: i18n } = this.app
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

  getModelIdentifierDescription() {
    return this.app.$i18n.t(
      'generativeAIModelType.ollamaModelIdentifierDescription'
    )
  }

  canPromptWithFiles() {
    return true
  }

  getOrder() {
    return 60
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
    const { $i18n: i18n } = this.app
    return i18n.t('generativeAIModelType.openRouter')
  }

  getSettings() {
    const { $i18n: i18n } = this.app
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

  getModelIdentifierDescription() {
    return this.app.$i18n.t(
      'generativeAIModelType.openRouterModelIdentifierDescription'
    )
  }

  canPromptWithFiles() {
    return true
  }

  getOrder() {
    return 70
  }
}

export class GoogleModelType extends GenerativeAIModelType {
  static getType() {
    return 'google'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('generativeAIModelType.google')
  }

  supportsLegacyWorkspaceSettings() {
    return false
  }

  getSettings() {
    const { $i18n: i18n } = this.app
    return [
      {
        key: 'api_key',
        label: i18n.t('generativeAIModelType.googleApiKeyLabel'),
        description: i18n.t('generativeAIModelType.googleApiKeyDescription'),
      },
      modelSettings(
        i18n.t('generativeAIModelType.googleModelsLabel'),
        i18n.t('generativeAIModelType.googleModelsDescription')
      ),
    ]
  }

  getModelIdentifierDescription() {
    return this.app.$i18n.t(
      'generativeAIModelType.googleModelIdentifierDescription'
    )
  }

  canPromptWithFiles() {
    return true
  }

  getOrder() {
    return 30
  }
}

export class GroqModelType extends GenerativeAIModelType {
  static getType() {
    return 'groq'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('generativeAIModelType.groq')
  }

  supportsLegacyWorkspaceSettings() {
    return false
  }

  getSettings() {
    const { $i18n: i18n } = this.app
    return [
      {
        key: 'api_key',
        label: i18n.t('generativeAIModelType.groqApiKeyLabel'),
        description: i18n.t('generativeAIModelType.groqApiKeyDescription'),
      },
      modelSettings(
        i18n.t('generativeAIModelType.groqModelsLabel'),
        i18n.t('generativeAIModelType.groqModelsDescription')
      ),
    ]
  }

  getModelIdentifierDescription() {
    return this.app.$i18n.t(
      'generativeAIModelType.groqModelIdentifierDescription'
    )
  }

  getOrder() {
    return 40
  }
}
