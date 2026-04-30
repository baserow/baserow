import { ApplicationType } from '@baserow/modules/core/applicationTypes'
import ApplicationContext from '@baserow/modules/whiteboard/components/application/ApplicationContext'
import WhiteboardForm from '@baserow/modules/whiteboard/components/form/WhiteboardForm'
import SidebarComponentWhiteboard from '@baserow/modules/whiteboard/components/sidebar/SidebarComponentWhiteboard'
import WhiteboardTemplate from '@baserow/modules/whiteboard/components/WhiteboardTemplate'
import WhiteboardTemplateSidebar from '@baserow/modules/whiteboard/components/sidebar/WhiteboardTemplateSidebar'
import { DEVELOPMENT_STAGES } from '@baserow/modules/core/constants'
import { pageFinished } from '@baserow/modules/core/utils/routing'
import { nextTick } from '#imports'

export class WhiteboardApplicationType extends ApplicationType {
  static getType() {
    return 'whiteboard'
  }

  getIconClass() {
    return 'iconoir-frame'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('applicationType.whiteboard')
  }

  getNamePlural() {
    const { $i18n: i18n } = this.app
    return i18n.t('applicationType.whiteboards')
  }

  getDescription() {
    const { $i18n: i18n } = this.app
    return i18n.t('applicationType.whiteboardDesc')
  }

  getDefaultName() {
    const { $i18n: i18n } = this.app
    return i18n.t('applicationType.whiteboardDefaultName')
  }

  supportsTrash() {
    return false
  }

  getApplicationContextComponent() {
    return ApplicationContext
  }

  getApplicationFormComponent() {
    return WhiteboardForm
  }

  getSidebarComponent() {
    return SidebarComponentWhiteboard
  }

  getTemplateSidebarComponent() {
    return WhiteboardTemplateSidebar
  }

  getTemplatesPageComponent() {
    return WhiteboardTemplate
  }

  getTemplatePage(application) {
    return {
      whiteboard: application,
    }
  }

  delete(application, { $router }) {
    $router.push({ name: 'dashboard' })
  }

  async select(application, { $router }) {
    try {
      await $router.push({
        name: 'whiteboard-application',
        params: {
          whiteboardId: application.id,
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
    return DEVELOPMENT_STAGES.ALPHA
  }

  getOrder() {
    return 85
  }
}
