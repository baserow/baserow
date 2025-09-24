import { Registerable } from '@baserow/modules/core/registry'

/**
 * The name plugin might be a bit confusing because you also have Nuxt plugins, but
 * this is not the same. A plugin can contain hooks for certain events such as when
 * a user account is created.
 */
export class BaserowPlugin extends Registerable {
  constructor(...args) {
    super(...args)
    this.type = this.getType()
  }

  /**
   * Hook that is called when a user creates a new account. This can for example be
   * used for submitting an analytical event.
   */
  userCreated(user, context) {}

  /**
   * Hook that is called when the initial workspace is created for a user. This happens
   * when the user cancels the onboarding, for example.
   */
  initialWorkspaceCreated(workspace) {}
  /**
   * Every registered plugin can have a component that's rendered at the top of the
   * left sidebar.
   */
  getImpersonateComponent() {
    return null
  }

  /**
   * Every registered plugin can have a component displaying a badge with the highest license type
   */
  getHighestLicenseTypeBadge() {
    return null
  }

  /**
   * Every registered plugin can display an additional item in the sidebar within
   * the workspace context.
   */
  getSidebarWorkspaceComponents(workspace) {
    return null
  }

  /**
   * Every registered plugin can display an additional item in the right sidebar within
   * the workspace context.
   */
  getRightSidebarWorkspaceComponents(workspace) {
    return null
  }

  /**
   * Every registered plugin can display additional items in the user context menu.
   */
  getUserContextComponents() {
    return null
  }

  /*
   * Every registered plugin can display a component in the links section of the
   * dashboard sidebar.
   */
  getDashboardResourceLinksComponent() {
    return null
  }

  /*
   * Every registered plugin can display a component in the `DashboardWorkspace`
   * component directly after the workspace name.
   */
  getDashboardWorkspacePlanBadge() {
    return null
  }

  getDashboardWorkspaceRowUsageComponent() {
    return null
  }

  /**
   * Because the dashboard could contain dynamic `getDashboardWorkspaceComponent` and
   * `getDashboardWorkspaceExtraComponent` components, it could be that additional data
   * must be fetched from the backend when the page first loads. This method can be
   * overwritten to do that.
   *
   * Optinally, a workspace id can be provided to fetch only data for a particular
   * workspace.
   */
  fetchAsyncDashboardData(context, data, workspaceId) {
    return data
  }

  /**
   * Tells core Baserow how new fetched data for a particular workspace
   * should be merged with previously fetched dashboard data from
   * fetchAsyncDashboardData()
   */
  mergeDashboardData(data, newData) {
    return data
  }

  /**
   * Every registered plugin can display a component in the `AuthRegister` component
   * directly at the bottom of the form. This component can be used to extend the
   * register functionality.
   */
  getRegisterComponent() {
    return null
  }

  /**
   * Every registered plugin can display a component in the `app.vue` layout. This
   * is the root component that's being used for every authenticated page in the app.
   */
  getAppLayoutComponent() {
    return null
  }

  /**
   * Every registered plugin can display multiple additional public share link options
   * which will be visible on the share public view context.
   */
  getAdditionalShareLinkOptions() {
    return []
  }

  /**
   * Every registered plugin can display multiple components to the head of the table
   * header. This will be positioned directly next to the name of the view.
   */
  getAdditionalTableHeaderComponents(view, isPublic) {
    return []
  }

  /**
   * Every registered plugin can display multiple additional context items in the
   * application context displayed by the sidebar when opening the context menu of a
   * application.
   * @returns {*[]}
   */
  getAdditionalApplicationContextComponents(workspace, application) {
    return []
  }

  /**
   * Every registered plugin can display multiple additional context items in the
   * table context displayed by the sidebar when opening the context menu of a
   * table.
   * @returns {*[]}
   */
  getAdditionalTableContextComponents(workspace, table) {
    return []
  }

  /**
   * Every registered plugin can display multiple additional context menu items in the
   * view context menu displayed at the top bar (three dots menu) in the View view.
   * @returns {*[]}
   */
  getAdditionalViewContextComponents(workspace, table, view) {
    return []
  }

  /**
   * Provides additional icons before 'standard' icons in the field header in a
   * grid view.
   *
   * @param workspace
   * @param view
   * @param field
   * @returns {*[]}
   */
  getGridViewFieldTypeIconsBefore(workspace, view, field) {
    return []
  }

  /**
   * If set, `getExtraSnapshotModalComponents` will allow plugins to decide what kind of
   * copy is shown in the snapshots modal's Alert box.
   */
  getExtraSnapshotModalComponents(workspace) {
    return null
  }

  /**
   * If set, `getExtraExportWorkspaceModalComponents` will allow plugins to decide what kind of
   * copy is shown in the export workspace modal's Alert box.
   */
  getExtraExportWorkspaceModalComponents(workspace) {
    return null
  }

  /**
   * If set, `getExtraImportWorkspaceModalComponents` will allow plugins to decide what kind of
   * copy is shown in the import workspace modal's Alert box.
   */
  getExtraImportWorkspaceModalComponents(workspace) {
    return null
  }

  /**
   * Some features are optionally enabled, this function will be called when the
   * $hasFeature directive is called on each plugin to check if any of the plugins
   * enable the particular feature.
   * @returns {boolean}
   */
  hasFeature(feature, forSpecificWorkspace) {
    return false
  }

  /**
   * Can return components that will be added to the admin instance settings page.
   */
  getSettingsPageComponents() {
    return []
  }

  /**
   * Can overwrite the help component shown on the dashboard page. Note that it can
   * only show one component, so if any plugin sets one, the original one will be
   * hidden, and those will be shown.
   */
  getDashboardHelpComponents() {
    return []
  }

  /**
   * Overwrite the logo component everywhere. If there are multiple plugins
   * providing a logo, then the one with the highest `getLogoComponentOrder` will be
   * used because we can only show one.
   */
  getLogoComponent() {
    return null
  }

  /**
   * If multiple logo components are returned, then the one with the highest order
   * will be placed.
   */
  getLogoComponentOrder() {
    return 50
  }

  /* Allow plugins to add scripts in the head section of a builder application */
  getBuilderApplicationHeaderAddition({ builder, mode }) {
    return {}
  }
}
