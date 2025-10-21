import {
  ServiceType,
  WorkflowActionServiceTypeMixin,
} from '@baserow/modules/core/serviceTypes'

import AiAgentServiceForm from '@baserow/modules/integrations/ai/components/services/AiAgentServiceForm'

export class AiAgentServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'ai_agent'
  }

  get name() {
    return this.app.i18n.t('serviceType.aiAgent')
  }

  get description() {
    return this.app.i18n.t('serviceType.aiAgentDescription')
  }

  getErrorMessage({ service }) {
    if (service === undefined) {
      return null
    }

    // Check if integration is selected
    if (!service.integration_id) {
      return this.app.i18n.t('serviceType.errorIntegrationMissing')
    }

    // Check if signature is provided
    if (!service.signature) {
      return this.app.i18n.t('serviceType.errorSignatureMissing')
    }

    // Validate signature format: must have at least one input and one output
    // Format: "input1: type, input2: type -> output1: type, output2: type"
    if (!this.isValidSignature(service.signature)) {
      return this.app.i18n.t('serviceType.errorSignatureInvalid')
    }

    // Check if prompt is provided
    if (!service.prompt) {
      return this.app.i18n.t('serviceType.errorPromptMissing')
    }

    return super.getErrorMessage({ service })
  }

  isValidSignature(signature) {
    // A valid signature must have the format: "inputs -> outputs"
    // Both inputs and outputs must be non-empty
    if (!signature || typeof signature !== 'string') {
      return false
    }

    const trimmed = signature.trim()
    if (!trimmed.includes('->')) {
      return false
    }

    const parts = trimmed.split('->')
    if (parts.length !== 2) {
      return false
    }

    const inputPart = parts[0].trim()
    const outputPart = parts[1].trim()

    // Both input and output parts must be non-empty
    return inputPart.length > 0 && outputPart.length > 0
  }

  getDataSchema(service) {
    return service.schema
  }

  get formComponent() {
    return AiAgentServiceForm
  }

  getOrder() {
    return 9
  }
}
