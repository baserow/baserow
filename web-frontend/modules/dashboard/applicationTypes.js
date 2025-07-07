import { ApplicationType } from '@baserow/modules/core/applicationTypes'
import ApplicationContext from '@baserow/modules/dashboard/components/application/ApplicationContext'
import DashboardForm from '@baserow/modules/dashboard/components/form/DashboardForm'
import SidebarComponentDashboard from '@baserow/modules/dashboard/components/sidebar/SidebarComponentDashboard'
import DashboardTemplateSidebar from '@baserow/modules/dashboard/components/sidebar/DashboardTemplateSidebar'
import DashboardTemplate from '@baserow/modules/dashboard/components/DashboardTemplate'
import { DEVELOPMENT_STAGES } from '@baserow/modules/core/constants'

export class DashboardApplicationType extends ApplicationType {
  static getType() {
    return 'dashboard'
  }

  getIconClass() {
    return 'baserow-icon-dashboard'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('applicationType.dashboard')
  }

  getNamePlural() {
    const { i18n } = this.app
    return i18n.t('applicationType.dashboards')
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('applicationType.dashboardDesc')
  }

  getDefaultName() {
    const { i18n } = this.app
    return i18n.t('applicationType.dashboardDefaultName')
  }

  supportsTrash() {
    return false
  }

  getApplicationContextComponent() {
    return ApplicationContext
  }

  getApplicationFormComponent() {
    return DashboardForm
  }

  getSidebarComponent() {
    return SidebarComponentDashboard
  }

  getTemplateSidebarComponent() {
    return DashboardTemplateSidebar
  }

  getTemplatesPageComponent() {
    return DashboardTemplate
  }

  getTemplatePage(application) {
    return {
      dashboard: application,
    }
  }

  delete(application, { $router }) {
    $router.push({ name: 'dashboard' })
  }

  async select(application, { $router }) {
    try {
      await $router.push({
        name: 'dashboard-application',
        params: {
          dashboardId: application.id,
        },
      })
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
