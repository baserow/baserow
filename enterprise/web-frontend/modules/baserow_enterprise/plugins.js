import { BaserowPlugin } from '@baserow/modules/core/plugins'
import EnterpriseFeatures from '@baserow_enterprise/features'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import { isAssistantConfigured } from '@baserow_enterprise/utils/assistant'
import { RestrictedViewOwnershipType } from '@baserow_enterprise/viewOwnershipTypes'
import { lazyComponent } from '@baserow/modules/core/utils/lazyComponent'

const ChatwootSupportSidebarWorkspace = lazyComponent(
  () => import('@baserow_enterprise/components/ChatwootSupportSidebarWorkspace')
)
const AuditLogSidebarWorkspace = lazyComponent(
  () => import('@baserow_enterprise/components/AuditLogSidebarWorkspace')
)
const MemberRolesApplicationContextItem = lazyComponent(
  () =>
    import('@baserow_enterprise/components/member-roles/MemberRolesApplicationContextItem')
)
const MemberRolesTableContextItem = lazyComponent(
  () =>
    import('@baserow_enterprise/components/member-roles/MemberRolesTableContextItem')
)
const MemberRolesViewContextItem = lazyComponent(
  () =>
    import('@baserow_enterprise/components/member-roles/MemberRolesViewContextItem')
)
const SnapshotModalWarning = lazyComponent(
  () => import('@baserow_enterprise/components/SnapshotModalWarning')
)
const EnterpriseSettings = lazyComponent(
  () => import('@baserow_enterprise/components/EnterpriseSettings')
)
const EnterpriseSettingsOverrideDashboardHelp = lazyComponent(
  () =>
    import('@baserow_enterprise/components/EnterpriseSettingsOverrideDashboardHelp')
)
const EnterpriseLogo = lazyComponent(
  () => import('@baserow_enterprise/components/EnterpriseLogo')
)
const AssistantSidebarItem = lazyComponent(
  () => import('@baserow_enterprise/components/assistant/AssistantSidebarItem')
)
const AssistantPanel = lazyComponent(
  () => import('@baserow_enterprise/components/assistant/AssistantPanel')
)
const AssistantDashboardPrompt = lazyComponent(
  () =>
    import('@baserow_enterprise/components/assistant/AssistantDashboardPrompt')
)
const DateDependencyMenuItem = lazyComponent(
  () =>
    import('@baserow_enterprise/components/dateDependency/DateDependencyMenuItem')
)
const DateDependencyFieldTypeIcon = lazyComponent(
  () =>
    import('@baserow_enterprise/components/dateDependency/DateDependencyFieldTypeIcon')
)
const ExportWorkspaceModalWarning = lazyComponent(
  () => import('@baserow_enterprise/components/ExportWorkspaceModalWarning')
)

export class EnterprisePlugin extends BaserowPlugin {
  static getType() {
    return 'enterprise'
  }

  getSidebarWorkspaceComponents(workspace) {
    const sidebarItems = []
    sidebarItems.push(AssistantSidebarItem)
    if (!this.app.$config.public.baserowDisableSupport) {
      sidebarItems.push(ChatwootSupportSidebarWorkspace)
    }
    sidebarItems.push(AuditLogSidebarWorkspace)
    return sidebarItems
  }

  getAdditionalApplicationContextComponents(workspace, application) {
    const applicationComponents = []
    const hasReadRolePermission = this.app.$hasPermission(
      'application.read_role',
      application,
      workspace.id
    )
    if (hasReadRolePermission) {
      applicationComponents.push(MemberRolesApplicationContextItem)
    }

    return applicationComponents
  }

  getAdditionalApplicationChildContextComponents(workspace, application, item) {
    if (application.type !== DatabaseApplicationType.getType()) {
      return []
    }

    const databaseComponents = []
    if (
      this.app.$hasPermission('database.table.read_role', item, workspace.id)
    ) {
      databaseComponents.push(MemberRolesTableContextItem)
    }
    databaseComponents.push(DateDependencyMenuItem)

    return databaseComponents
  }

  getRightSidebarWorkspaceComponents(workspace) {
    return isAssistantConfigured(this.app, workspace) ? [AssistantPanel] : []
  }

  getGridViewFieldTypeIconsBefore(workspace, view, field) {
    const out = []
    out.push(DateDependencyFieldTypeIcon)
    return out
  }

  getAdditionalViewContextComponents(workspace, table, view) {
    const components = []
    if (
      this.app.$hasPermission(
        'database.table.view.read_role',
        view,
        workspace.id
      ) &&
      // Assigning a role to a user on view level only actually does something for
      // the restricted view. So we're only showing the modal there.
      view.ownership_type === RestrictedViewOwnershipType.getType()
    ) {
      components.push(MemberRolesViewContextItem)
    }
    components.push(DateDependencyMenuItem)
    return components
  }

  getExtraSnapshotModalComponents(workspace) {
    const rbacSupport = this.app.$hasFeature(
      EnterpriseFeatures.RBAC,
      workspace.id
    )
    return rbacSupport ? SnapshotModalWarning : null
  }

  getExtraExportWorkspaceModalComponents(workspace) {
    const rbacSupport = this.app.$hasFeature(
      EnterpriseFeatures.RBAC,
      workspace.id
    )
    return rbacSupport ? ExportWorkspaceModalWarning : null
  }

  getSettingsPageComponents() {
    return [EnterpriseSettings]
  }

  getDashboardTopComponents(workspace) {
    // The component decides whether the assistant is available, because that
    // depends on permissions that are loaded after the page first renders.
    return [AssistantDashboardPrompt]
  }

  getDashboardHelpComponents() {
    if (this.app.$hasFeature(EnterpriseFeatures.ENTERPRISE_SETTINGS)) {
      return [EnterpriseSettingsOverrideDashboardHelp]
    } else {
      return []
    }
  }

  getLogoComponent() {
    if (this.app.$hasFeature(EnterpriseFeatures.ENTERPRISE_SETTINGS)) {
      return EnterpriseLogo
    } else {
      return null
    }
  }

  getLogoComponentOrder() {
    return 100
  }

  /**
   * This method can be used to hide certain features in `EnterpriseFeatures.vue`.
   * If the array contains `[EnterpriseFeatures.RBAC]`, for example, then that entry
   * will be hidden in the features.
   */
  getVisuallyHiddenFeatures() {
    return []
  }

  /**
   * Adds the custom CSS/JS defined for this builder.
   */
  getBuilderApplicationHeaderAddition({ builder, mode }) {
    const customCodeBase =
      mode === 'preview'
        ? `${this.app.$config.public.publicBackendUrl}/api/builder/preview/${builder.id}/custom-code`
        : `${this.app.$config.public.publicBackendUrl}/api/custom_code/${builder.id}`
    const css = `${customCodeBase}/css/${mode === 'preview' ? '' : 'public/'}`
    const js = `${customCodeBase}/js/${mode === 'preview' ? '' : 'public/'}`

    const script = []
    const link = []

    builder.scripts.forEach((s) => {
      if (!s.url) {
        return
      }

      const crossorigin =
        s.crossorigin === 'credentials'
          ? 'use-credentials'
          : s.crossorigin === 'anonymous'
            ? 'anonymous'
            : null

      if (s.type === 'javascript') {
        script.push({
          src: s.url,
          crossorigin,
          defer: s.load_type === 'defer',
          async: s.load_type === 'async',
          tagPosition: 'bodyClose',
        })
      }

      if (s.type === 'stylesheet') {
        script.push({
          rel: 'stylesheet',
          href: s.url,
          crossorigin,
          tagPosition: 'bodyClose',
        })
      }
    })

    if (builder.custom_code.css) {
      link.push({
        rel: 'stylesheet',
        href: css,
        crossorigin: mode === 'preview' ? 'use-credentials' : null,
        tagPosition: 'bodyClose',
      })
    }
    if (builder.custom_code.js) {
      script.push({
        src: js,
        crossorigin: mode === 'preview' ? 'use-credentials' : null,
        defer: true,
        tagPosition: 'bodyClose',
      })
    }

    return {
      link,
      script,
    }
  }
}
