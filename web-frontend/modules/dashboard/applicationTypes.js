import { getApplicationComponent } from '@baserow/modules/core/utils/applicationBundles'
import { ApplicationType } from '@baserow/modules/core/applicationTypes'

import { DEVELOPMENT_STAGES } from '@baserow/modules/core/constants'
import { pageFinished } from '@baserow/modules/core/utils/routing'
import { nextTick } from '#imports'

export class DashboardApplicationType extends ApplicationType {
  /** Applications without child navigation open their page from the sidebar. */
  async selectFromSidebar(application) {
    await this.app.$store.dispatch('application/select', application)
    await this.select(application, this.app)
  }

  static getType() {
    return 'dashboard'
  }

  getIconClass() {
    return 'baserow-icon-dashboard'
  }

  getIconColor() {
    return 'magenta'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('applicationType.dashboard')
  }

  getNamePlural() {
    const { $i18n: i18n } = this.app
    return i18n.t('applicationType.dashboards')
  }

  getViewLabel() {
    const { $i18n: i18n } = this.app
    return i18n.t('applicationType.viewDashboard')
  }

  getDescription() {
    const { $i18n: i18n } = this.app
    return i18n.t('applicationType.dashboardDesc')
  }

  getDefaultName() {
    const { $i18n: i18n } = this.app
    return i18n.t('applicationType.dashboardDefaultName')
  }

  supportsTrash() {
    return false
  }

  getApplicationContextComponent() {
    return getApplicationComponent(this.app, 'dashboard', 'ApplicationContext')
  }

  getApplicationFormComponent() {
    return getApplicationComponent(this.app, 'dashboard', 'DashboardForm')
  }

  getSidebarComponent() {
    return getApplicationComponent(
      this.app,
      'dashboard',
      'SidebarComponentDashboard'
    )
  }

  getTemplateSidebarComponent() {
    return getApplicationComponent(
      this.app,
      'dashboard',
      'DashboardTemplateSidebar'
    )
  }

  getTemplatesPageComponent() {
    return getApplicationComponent(this.app, 'dashboard', 'DashboardTemplate')
  }

  getTemplatePage(application) {
    return {
      dashboard: application,
    }
  }

  delete(application, { $router }) {
    if (application._.selected) {
      $router.push({
        name: 'workspace',
        params: { workspaceId: application.workspace.id },
      })
    }
  }

  async select(application, { $router }) {
    try {
      await $router.push({
        name: 'dashboard-application',
        params: {
          dashboardId: application.id,
        },
      })
      await pageFinished(this.app)
      await nextTick()
    } catch (error) {
      if (error.name !== 'NavigationDuplicated') {
        throw error
      }
    }
  }

  get developmentStage() {
    return DEVELOPMENT_STAGES.BETA
  }

  getOrder() {
    return 80
  }
}
