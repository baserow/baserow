import {
  ServiceType,
  WorkflowActionServiceTypeMixin,
} from '@baserow/modules/core/serviceTypes'
import { AIIntegrationType } from '@baserow/modules/integrations/ai/integrationTypes'
import AIAgentServiceForm from '@baserow/modules/integrations/ai/components/services/AIAgentServiceForm'

export class AIAgentServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'ai_agent'
  }

  get name() {
    return this.app.i18n.t('serviceType.aiAgent')
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
    return this.app.i18n.t('serviceType.aiAgentDescription')
  }

  getDataSchema(service) {
    return service.schema
  }

  getErrorMessage({ service }) {
    if (service === undefined) {
      return null
    }

    if (service.ai_generative_ai_model === undefined) {
      // we are in public mode so no properties are available let's quit.
      return null
    }

    if (!service.ai_generative_ai_type) {
      return this.app.i18n.t('serviceType.errorNoAIProviderSelected')
    }
    if (!service.ai_generative_ai_model) {
      return this.app.i18n.t('serviceType.errorNoAIModelSelected')
    }
    if (!service.ai_prompt.formula) {
      return this.app.i18n.t('serviceType.errorNoPromptProvided')
    }
    if (service.ai_output_type === 'choice') {
      // Check if choices array is empty or has no valid choices
      if (
        !service.ai_choices ||
        !Array.isArray(service.ai_choices) ||
        service.ai_choices.length === 0 ||
        service.ai_choices.every((c) => !c || !c.trim())
      ) {
        return this.app.i18n.t('serviceType.errorNoChoicesProvided')
      }
    }
    return super.getErrorMessage({ service })
  }

  getDescription(service, application) {
    let description = this.name

    if (service.ai_generative_ai_model) {
      description += ` - ${service.ai_generative_ai_model}`
    }

    if (this.isInError({ service })) {
      description += ` - ${this.getErrorMessage({ service })}`
    }

    return description
  }

  getOrder() {
    return 9
  }
}
