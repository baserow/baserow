import { ViewOwnershipType } from '@baserow/modules/database/viewOwnershipTypes'
import EnterpriseFeatures from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { RBACPaidFeature } from '@baserow_enterprise/paidFeatures'
import { FormViewType } from '@baserow/modules/database/viewTypes.js'

export class RestrictedViewOwnershipType extends ViewOwnershipType {
  static getType() {
    return 'restricted'
  }

  getName() {
    const { $i18n } = this.app
    return $i18n.t('viewOwnershipType.restricted')
  }

  getDescription() {
    const { $i18n } = this.app
    return $i18n.t('viewOwnershipType.restrictedDescription')
  }

  getFeatureName() {
    const { $i18n } = this.app
    return $i18n.t('enterpriseFeatures.restrictedViews')
  }

  getIconClass() {
    return 'iconoir-shield-check'
  }

  isCompatibleWithViewType(viewType) {
    return viewType.type !== FormViewType.getType()
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

  fetchingFieldsRequiresViewId(database, table, view) {
    const canListFields = this.app.$hasPermission(
      'database.table.list_fields',
      table,
      database.workspace.id
    )
    // The view query parameter must be added if the user does not have permissions to
    // list all the fields of the table. If the view param is added, it will only list
    // the fields related to this view.
    return !canListFields
  }

  _canUpdateFieldOptions(view, database) {
    return this.app.$hasPermission(
      'database.table.view.update_field_options',
      view,
      database.workspace.id
    )
  }

  _getHiddenFieldIds(fields, view, storePrefix) {
    const viewType = this.app.$registry.get('view', view.type)
    const visibleFields = viewType.getVisibleFieldsInOrder(
      { $store: this.app.$store },
      fields,
      view,
      storePrefix
    )
    const visibleFieldIds = new Set(visibleFields.map((f) => f.id))
    return new Set(
      fields.filter((f) => !visibleFieldIds.has(f.id)).map((f) => f.id)
    )
  }

  getSortContextWarning(view, fields, database, storePrefix) {
    // If a user has the ability to update the field options, then they can hide and
    // show fields. If they don't have that ability, then this warning should never be
    // shown because they can't control the hidden fields anyway.
    if (!this._canUpdateFieldOptions(view, database)) {
      return null
    }
    const viewType = this.app.$registry.get('view', view.type)
    const visibleFields = viewType.getVisibleFieldsInOrder(
      { $store: this.app.$store },
      fields,
      view,
      storePrefix
    )
    const hiddenFieldIds = this._getHiddenFieldIds(fields, view, storePrefix)
    if (hiddenFieldIds.size === 0) {
      return null
    }
    if (!view.sortings.some((s) => hiddenFieldIds.has(s.field))) {
      return null
    }
    return this.app.$i18n.t('viewSortContext.hiddenFieldWarning')
  }

  getGroupByContextWarning(view, fields, database, storePrefix) {
    // If a user has the ability to update the field options, then they can hide and
    // show fields. If they don't have that ability, then this warning should never be
    // shown because they can't control the hidden fields anyway.
    if (!this._canUpdateFieldOptions(view, database)) {
      return null
    }
    const hiddenFieldIds = this._getHiddenFieldIds(fields, view, storePrefix)
    if (hiddenFieldIds.size === 0) {
      return null
    }
    if (!view.group_bys.some((g) => hiddenFieldIds.has(g.field))) {
      return null
    }
    return this.app.$i18n.t('viewGroupByContext.hiddenFieldWarning')
  }

  getDecoratorContextWarning(view, fields, database, storePrefix) {
    // If a user has the ability to update the field options, then they can hide and
    // show fields. If they don't have that ability, then this warning should never be
    // shown because they can't control the hidden fields anyway.
    if (!this._canUpdateFieldOptions(view, database)) {
      return null
    }
    const hiddenFieldIds = this._getHiddenFieldIds(fields, view, storePrefix)
    if (hiddenFieldIds.size === 0) {
      return null
    }
    return this.app.$i18n.t('viewDecorator.hiddenFieldWarning')
  }
}
