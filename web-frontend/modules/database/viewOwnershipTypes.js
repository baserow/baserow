import { Registerable } from '@baserow/modules/core/registry'

export class ViewOwnershipType extends Registerable {
  /**
   * A human readable name of the view ownership type.
   */
  getName() {
    return null
  }

  /**
   * A short human readable description of the view ownership type that will be
   * shown to the user when creating the view.
   */
  getDescription() {
    return null
  }

  /**
   * A human readable name of the feature it belongs to.
   */
  getFeatureName() {
    return this.getName()
  }

  /**
   * The icon for the type in the form of CSS class.
   */
  getIconClass() {
    return null
  }

  /**
   * Indicates if the view ownership type is disabled.
   */
  isDeactivated(workspaceId) {
    return false
  }

  /**
   * Text description when deactivated.
   */
  getDeactivatedText() {
    return null
  }

  /**
   * Show deactivated modal when selecting.
   */
  getDeactivatedModal() {
    return null
  }

  /**
   * The order in which workspaces of diff. view ownership
   * types appear in the list views.
   */
  getListViewTypeSort() {
    return 50
  }

  /**
   * @return object
   */
  serialize() {
    return {
      type: this.type,
      name: this.getName(),
    }
  }

  /**
   * A component that's added to the context menu of the view that can be used to,
   * for example, change the ownership type of the view. By default, it doesn't
   * register a component.
   */
  getChangeOwnershipTypeMenuItemComponent() {
    return null
  }

  userCanTryCreate(table, workspaceId) {
    return this.app.$hasPermission(
      'database.table.create_view',
      table,
      workspaceId
    )
  }

  /**
   * Hook that can be used to change the realtime page payload before subscribing to
   * the page. This can be used to subscribe to a different page with different
   * real-time events, if needed.
   */
  enhanceRealtimePagePayload(database, table, view, realtimePage) {
    return realtimePage
  }
}

export class CollaborativeViewOwnershipType extends ViewOwnershipType {
  static getType() {
    return 'collaborative'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewOwnershipType.collaborative')
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('viewOwnershipType.collaborativeDescription')
  }

  getIconClass() {
    return 'iconoir-group'
  }
}
