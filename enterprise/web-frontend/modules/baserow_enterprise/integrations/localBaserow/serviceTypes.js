import { WorkflowActionServiceTypeMixin } from '@baserow/modules/core/serviceTypes'
import { LocalBaserowListRowsServiceType } from '@baserow/modules/integrations/localBaserow/serviceTypes'
import EnterpriseFeatures from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { SemanticSearchPaidFeature } from '@baserow_enterprise/paidFeatures'
import LocalBaserowSemanticSearchServiceForm from '@baserow_enterprise/integrations/localBaserow/components/services/LocalBaserowSemanticSearchServiceForm'

export class LocalBaserowSemanticSearchServiceType extends WorkflowActionServiceTypeMixin(
  LocalBaserowListRowsServiceType
) {
  static getType() {
    return 'local_baserow_semantic_search'
  }

  get name() {
    return this.app.$i18n.t('serviceType.localBaserowSemanticSearch')
  }

  get description() {
    return this.app.$i18n.t('serviceType.localBaserowSemanticSearchDescription')
  }

  get icon() {
    return 'iconoir-search'
  }

  get formComponent() {
    return LocalBaserowSemanticSearchServiceForm
  }

  // Results are ordered by relevance, so they can't be sorted or searched.
  get adhocHeaderComponent() {
    return null
  }

  /**
   * The values of a result's row are nested in its `row` property, because a
   * field can have any name, including the names of the other properties.
   */
  getRowSchemaProperties(service) {
    return this.getSchemaProperties(service)?.row?.properties || {}
  }

  getDefaultCollectionFields(service) {
    return this.getCollectionFieldsForProperties(
      this.getRowSchemaProperties(service),
      'current_record.row'
    )
  }

  prepareValuePath(service, path) {
    const [property, field, ...rest] = path
    const title = this.getRowSchemaProperties(service)[field]?.title
    if (property === 'row' && title) {
      return [property, title, ...rest]
    }
    return path
  }

  getRecordName(service, record) {
    const primaryField = Object.values(
      this.getRowSchemaProperties(service)
    ).find(({ metadata }) => metadata?.primary)
    return primaryField ? record.row?.[primaryField.title] : ''
  }

  getMaxResultLimit(service) {
    return service.max_results
  }

  isAvailable() {
    return !!this.app.$store.getters['settings/get'].semantic_search?.available
  }

  hasFeature(workspace) {
    return this.app.$hasFeature(
      EnterpriseFeatures.SEMANTIC_SEARCH,
      workspace.id
    )
  }

  isDeactivatedReason({ workspace }) {
    if (!this.isAvailable()) {
      return this.app.$i18n.t('serviceType.semanticSearchUnavailable')
    }
    if (workspace && !this.hasFeature(workspace)) {
      return this.app.$i18n.t('enterprise.deactivated')
    }
    return null
  }

  getDeactivatedClickModal({ workspace }) {
    if (this.isAvailable() && workspace && !this.hasFeature(workspace)) {
      return [
        PaidFeaturesModal,
        { 'initial-selected-type': SemanticSearchPaidFeature.getType() },
      ]
    }
    return null
  }

  getOrder() {
    return 25
  }
}
