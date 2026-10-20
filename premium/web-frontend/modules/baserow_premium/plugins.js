import { BaserowPlugin } from '@baserow/modules/core/plugins'
import { lazyComponent } from '@baserow/modules/core/utils/lazyComponent'

const Impersonate = lazyComponent(
  () => import('@baserow_premium/components/sidebar/Impersonate')
)
const HighestLicenseTypeBadge = lazyComponent(
  () => import('@baserow_premium/components/sidebar/HighestLicenseTypeBadge')
)
const PremiumViewOptions = lazyComponent(
  () => import('@baserow_premium/components/views/PremiumViewOptions')
)
const PublicViewExportMenuItem = lazyComponent(
  () => import('@baserow_premium/components/views/PublicViewExportMenuItem')
)
const PremiumDashboardShareOptions = lazyComponent(
  () =>
    import('@baserow_premium/components/dashboard/PremiumDashboardShareOptions')
)

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
