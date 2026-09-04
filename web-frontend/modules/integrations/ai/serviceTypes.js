import {
  ServiceType,
  WorkflowActionServiceTypeMixin,
} from '@baserow/modules/core/serviceTypes'
import { AIIntegrationType } from '@baserow/modules/integrations/ai/integrationTypes'
import AIAgentServiceForm from '@baserow/modules/integrations/ai/components/services/AIAgentServiceForm'
import { getEnabledModelsForAIProviderFeature } from '@baserow/modules/core/aiProviderModelFeatureTypes'
import { AIAgentAIProviderModelFeatureType } from '@baserow/modules/integrations/ai/aiProviderModelFeatureTypes'
import { FF_AI_PROVIDERS } from '@baserow/modules/core/plugins/featureFlags'
import { getEffectiveAIAgentModels } from '@baserow/modules/integrations/ai/utils'

export class AIAgentServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'ai_agent'
  }

  get name() {
    return this.app.$i18n.t('serviceType.aiAgent')
  }

  get icon() {
    return 'iconoir-sparks'
  }

  get formComponent() {
    return AIAgentServiceForm
  }

  get integrationType() {
    return this.app.$registry.get('integration', AIIntegrationType.getType())
  }

  get description() {
    return this.app.$i18n.t('serviceType.aiAgentDescription')
  }

  getDataSchema(service) {
    return service.schema
  }

  getEffectiveModels({ service, workspace, application }) {
    if (!workspace) {
      return null
    }

    const providerType = service.ai_generative_ai_type
    const modelType =
      this.app.$registry.getAll('generativeAIModel')[providerType] || null
    const workspaceModels = getEnabledModelsForAIProviderFeature(
      workspace,
      AIAgentAIProviderModelFeatureType.getType(),
      true
    )[providerType]

    let integrationSettings = null
    if (application && service.integration_id) {
      const integration = this.app.$store.getters[
        'integration/getIntegrationById'
      ](application, service.integration_id)
      // Avoid reporting a false configuration error while the application's
      // integrations are still loading.
      if (!integration) {
        return null
      }
      integrationSettings = integration.ai_settings?.[providerType]
    }

    return getEffectiveAIAgentModels({
      workspaceModels: workspaceModels || [],
      integrationSettings,
      modelType,
    })
  }

  getErrorMessage({ service, workspace = null, application = null }) {
    if (service === undefined) {
      return null
    }

    if (service.ai_generative_ai_model === undefined) {
      // we are in public mode so no properties are available let's quit.
      return null
    }

    if (!service.ai_generative_ai_type) {
      return this.app.$i18n.t('serviceType.errorNoAIProviderSelected')
    }
    if (!service.ai_generative_ai_model) {
      return this.app.$i18n.t('serviceType.errorNoAIModelSelected')
    }
    if (this.app.$featureFlagIsEnabled(FF_AI_PROVIDERS)) {
      const effectiveModels = this.getEffectiveModels({
        service,
        workspace,
        application,
      })
      if (
        effectiveModels !== null &&
        !effectiveModels.includes(service.ai_generative_ai_model)
      ) {
        return this.app.$i18n.t('serviceType.errorAIModelUnavailable')
      }
    }
    if (!service.ai_prompt.formula) {
      return this.app.$i18n.t('serviceType.errorNoPromptProvided')
    }
    if (service.ai_output_type === 'choice') {
      // Check if choices array is empty or has no valid choices
      if (
        !service.ai_choices ||
        !Array.isArray(service.ai_choices) ||
        service.ai_choices.length === 0 ||
        service.ai_choices.every((c) => !c || !c.trim())
      ) {
        return this.app.$i18n.t('serviceType.errorNoChoicesProvided')
      }
    }
    return super.getErrorMessage({ service, workspace, application })
  }

  getDescription(service, application) {
    let description = this.name

    if (service.ai_generative_ai_model) {
      description += ` - ${service.ai_generative_ai_model}`
    }

    const workspaceId = application?.workspace?.id ?? application?.workspace
    const workspace = workspaceId
      ? this.app.$store.getters['workspace/get'](workspaceId)
      : null
    const validationContext = { service, workspace, application }
    if (this.isInError(validationContext)) {
      description += ` - ${this.getErrorMessage(validationContext)}`
    }

    return description
  }

  getOrder() {
    return 9
  }
}
