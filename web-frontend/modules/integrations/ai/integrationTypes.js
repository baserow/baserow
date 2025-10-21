import { IntegrationType } from '@baserow/modules/core/integrationTypes'
import LMForm from '@baserow/modules/integrations/ai/components/integrations/LMForm'

export class LMIntegrationType extends IntegrationType {
  static getType() {
    return 'lm'
  }

  get name() {
    return this.app.i18n.t('integrationType.lm')
  }

  get iconClass() {
    return 'iconoir-sparks'
  }

  getSummary(integration) {
    return this.app.i18n.t('lmIntegrationType.lmSummary', {
      model: integration.model,
    })
  }

  get formComponent() {
    return LMForm
  }

  getDefaultValues() {
    return {
      model: '',
      api_key: '',
      api_base_url: '',
    }
  }

  getOrder() {
    return 21
  }
}
