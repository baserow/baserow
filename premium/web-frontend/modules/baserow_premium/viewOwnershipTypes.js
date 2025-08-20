import { ViewOwnershipType } from '@baserow/modules/database/viewOwnershipTypes'
import PremiumFeatures from '@baserow_premium/features'
import ViewOwnershipMenuLink from '@baserow_premium/components/views/ViewOwnershipMenuLink'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { PersonalViewsPaidFeature } from '@baserow_premium/paidFeatures'

export class PersonalViewOwnershipType extends ViewOwnershipType {
  static getType() {
    return 'personal'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewOwnershipType.personal')
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('viewOwnershipType.personalDescription')
  }

  getFeatureName() {
    const { i18n } = this.app
    return i18n.t('premiumFeatures.personalViews')
  }

  getIconClass() {
    return 'iconoir-user'
  }

  isDeactivated(workspaceId) {
    return !this.app.$hasFeature(PremiumFeatures.PREMIUM, workspaceId)
  }

  getDeactivatedText() {
    return this.app.i18n.t('premium.deactivated')
  }

  getDeactivatedModal() {
    return [
      PaidFeaturesModal,
      { 'initial-selected-type': PersonalViewsPaidFeature.getType() },
    ]
  }

  getListViewTypeSort() {
    return 40
  }

  /**
   * Returns the component that should be used in the menu for changing the
   * ownership type for the view.
   */
  getChangeOwnershipTypeMenuItemComponent() {
    return ViewOwnershipMenuLink
  }

  userCanTryCreate(table, workspaceId) {
    return this.app.$hasPermission(
      'database.table.create_and_use_personal_view',
      table,
      workspaceId
    )
  }
}
