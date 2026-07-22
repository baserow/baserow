import { defineAsyncComponent, hydrateOnIdle } from 'vue'
import { RowModalSidebarType } from '@baserow/modules/database/rowModalSidebarTypes'
import PremiumFeatures from '@baserow_premium/features'

const RowCommentsSidebar = defineAsyncComponent({
  loader: () =>
    import('@baserow_premium/components/row_comments/RowCommentsSidebar'),
  hydrate: hydrateOnIdle(),
})
const RowEditModalCommentNotificationMode = defineAsyncComponent({
  loader: () =>
    import('@baserow_premium/components/row_comments/RowEditModalCommentNotificationMode'),
  hydrate: hydrateOnIdle(),
})

export class CommentsRowModalSidebarType extends RowModalSidebarType {
  static getType() {
    return 'comments'
  }

  getName() {
    return this.app.$i18n.t('rowCommentSidebar.name')
  }

  getComponent() {
    return RowCommentsSidebar
  }

  isDeactivated(database, table, readOnly, view = null) {
    const hasTablePermission = this.app.$hasPermission(
      'database.table.list_comments',
      table,
      database.workspace.id
    )
    const hasViewPermission =
      view &&
      this.app.$hasPermission(
        'database.table.view.list_comments',
        view,
        database.workspace.id
      )
    return !hasTablePermission && !hasViewPermission
  }

  isSelectedByDefault(database) {
    return this.app.$hasFeature(PremiumFeatures.PREMIUM, database.workspace.id)
  }

  getOrder() {
    return 0
  }

  getActionComponent(row) {
    // Return this component only if the row provides the metadata to show the
    // notification mode context properly.
    if (row._?.metadata) {
      return RowEditModalCommentNotificationMode
    }
  }
}
