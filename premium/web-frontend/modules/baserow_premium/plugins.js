import { BaserowPlugin } from '@baserow/modules/core/plugins'
import Impersonate from '@baserow_premium/components/sidebar/Impersonate'
import HighestLicenseTypeBadge from '@baserow_premium/components/sidebar/HighestLicenseTypeBadge'
import PremiumViewOptions from '@baserow_premium/components/views/PremiumViewOptions'
import PublicViewExportMenuItem from '@baserow_premium/components/views/PublicViewExportMenuItem'
import PremiumDashboardShareOptions from '@baserow_premium/components/dashboard/PremiumDashboardShareOptions'

export class PremiumPlugin extends BaserowPlugin {
  static getType() {
    return 'premium'
  }

  getImpersonateComponent() {
    return Impersonate
  }

  getHighestLicenseTypeBadge() {
    return HighestLicenseTypeBadge
  }

  getAdditionalShareLinkOptions() {
    return [PremiumViewOptions]
  }

  getAdditionalDashboardShareLinkOptions() {
    return [PremiumDashboardShareOptions]
  }

  getAdditionalPublicViewMenuItems(view) {
    return view.allow_public_export ? [PublicViewExportMenuItem] : []
  }

  hasFeature(feature, forSpecificWorkspace) {
    return this.app.$licenseHandler.hasFeature(feature, forSpecificWorkspace)
  }

  /**
   * A hook to provide different action buttons to the premium features modal.
   */
  getPremiumModalButtonsComponent() {
    return null
  }
}
