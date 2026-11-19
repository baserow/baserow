import { getApplicationComponent } from '@baserow/modules/core/utils/applicationBundles'
import { PremiumRuntimePlugin } from '@baserow_premium/pluginsRuntime'
import Impersonate from '@baserow_premium/components/sidebar/Impersonate'
import HighestLicenseTypeBadge from '@baserow_premium/components/sidebar/HighestLicenseTypeBadge'

export class PremiumPlugin extends PremiumRuntimePlugin {
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
    return [getApplicationComponent(this.app, 'database', 'PremiumViewOptions')]
  }

  getAdditionalDashboardShareLinkOptions() {
    return [
      getApplicationComponent(
        this.app,
        'dashboard',
        'PremiumDashboardShareOptions'
      ),
    ]
  }

  getAdditionalPublicViewMenuItems(view) {
    return view.allow_public_export
      ? [
          getApplicationComponent(
            this.app,
            'database',
            'PublicViewExportMenuItem'
          ),
        ]
      : []
  }

  /**
   * A hook to provide different action buttons to the premium features modal.
   */
  getPremiumModalButtonsComponent() {
    return null
  }
}
