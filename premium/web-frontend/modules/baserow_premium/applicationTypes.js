import { getApplicationComponent } from '@baserow/modules/core/utils/applicationBundles'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'

export class PremiumDatabaseApplicationType extends DatabaseApplicationType {
  getRowExpandButtonComponent() {
    return getApplicationComponent(
      this.app,
      'database',
      'GridViewRowExpandButtonWithCommentCount'
    )
  }
}
