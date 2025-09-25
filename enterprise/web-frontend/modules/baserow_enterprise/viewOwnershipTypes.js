import { ViewOwnershipType } from '@baserow/modules/database/viewOwnershipTypes'
import EnterpriseFeatures from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { RBACPaidFeature } from '@baserow_enterprise/paidFeatures'

export class RestrictedViewOwnershipType extends ViewOwnershipType {
  static getType() {
    return 'restricted'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewOwnershipType.restricted')
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('viewOwnershipType.restrictedDescription')
  }

  getFeatureName() {
    const { i18n } = this.app
    return i18n.t('enterpriseFeatures.restrictedViews')
  }

  getIconClass() {
    return 'iconoir-shield-check'
  }

  isDeactivated(workspaceId) {
    return !this.app.$hasFeature(EnterpriseFeatures.RBAC, workspaceId)
  }

  getDeactivatedText() {
    return this.app.i18n.t('enterprise.deactivated')
  }

  getDeactivatedModal() {
    return [
      PaidFeaturesModal,
      { 'initial-selected-type': RBACPaidFeature.getType() },
    ]
  }

  getListViewTypeSort() {
    return 30
  }

  enhanceRealtimePagePayload(database, table, view, payload) {
    const canListenToTableEvents = this.app.$hasPermission(
      'database.table.listen_to_all',
      table,
      database.workspace.id
    )
    const canCreateFilters = this.app.$hasPermission(
      'database.table.view.create_filter',
      view,
      database.workspace.id
    )
    if (canListenToTableEvents && canCreateFilters) {
      return super.enhanceRealtimePagePayload(database, table, view, payload)
    }

    payload.page = 'restricted_view'
    payload.params = { restricted_view_id: view.id }
    return payload
  }
}
