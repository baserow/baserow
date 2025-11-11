import { Registerable } from '@baserow/modules/core/registry'
import GeneralSidePanel from '@baserow/modules/builder/components/page/sidePanels/GeneralSidePanel'
import StyleSidePanel from '@baserow/modules/builder/components/page/sidePanels/StyleSidePanel'
import VisibilitySidePanel from '@baserow/modules/builder/components/page/sidePanels/VisibilitySidePanel'
import EventsSidePanel from '@baserow/modules/builder/components/page/sidePanels/EventsSidePanel'

export class pageSidePanelType extends Registerable {
  get label() {
    return null
  }

  get component() {
    return null
  }

  /**
   * The message which appears in the tooltip when the page side panel
   * detects that the tab should be deactivated.
   * @returns {string}
   */
  getDeactivatedText() {
    return ''
  }

  /**
   * The message which appears in the tooltip when the page side panel
   * is misconfigured and in-error.
   * @returns {string}
   */
  getErrorMessage(applicationContext) {
    return null
  }

  isDeactivated(element) {
    return false
  }

  getOrder() {
    return this.order
  }

  /**
   * Returns whether this side panel is in error, or not. Allows us to append
   * an error icon after the panel title so that the page designer can be
   * informed.
   * @param applicationContext
   * @returns {boolean}
   */
  isInError(applicationContext) {
    return Boolean(this.getErrorMessage(applicationContext))
  }
}

export class GeneralPageSidePanelType extends pageSidePanelType {
  static getType() {
    return 'general'
  }

  get label() {
    return this.app.i18n.t('pageSidePanelType.general')
  }

  get component() {
    return GeneralSidePanel
  }

  getOrder() {
    return 10
  }
}

export class StylePageSidePanelType extends pageSidePanelType {
  static getType() {
    return 'style'
  }

  get label() {
    return this.app.i18n.t('pageSidePanelType.style')
  }

  get component() {
    return StyleSidePanel
  }

  getOrder() {
    return 20
  }
}

export class VisibilityPageSidePanelType extends pageSidePanelType {
  static getType() {
    return 'visibility'
  }

  get label() {
    return this.app.i18n.t('pageSidePanelType.visibility')
  }

  get component() {
    return VisibilitySidePanel
  }

  getOrder() {
    return 30
  }
}

export class EventsPageSidePanelType extends pageSidePanelType {
  static getType() {
    return 'events'
  }

  get label() {
    return this.app.i18n.t('pageSidePanelType.events')
  }

  get component() {
    return EventsSidePanel
  }

  /**
   * The message which appears in the tooltip when the events page side panel
   * detects that the selected element doesn't support any events.
   * @returns {string}
   */
  getDeactivatedText() {
    const { i18n } = this.app
    return i18n.t('pageSidePanelType.eventsTabDeactivatedNoEvents')
  }

  isDeactivated(element) {
    const elementType = this.app.$registry.get('element', element.type)
    return elementType.getEvents(element).length === 0
  }

  getOrder() {
    return 40
  }

  /**
   * The message which appears in the tooltip when the events page side panel
   * is misconfigured, as one or more workflow actions are in-error.
   * @returns {string}
   */
  getErrorMessage(applicationContext) {
    const { element, builder } = applicationContext

    // If we don't have an element, then this element type
    // doesn't support events, so it can't be in-error.
    if (element) {
      const elementPage = this.app.store.getters['page/getById'](
        builder,
        element.page_id
      )

      const workflowActions = this.app.store.getters[
        'builderWorkflowAction/getElementWorkflowActions'
      ](elementPage, element.id)

      const hasActionInError = workflowActions.some((workflowAction) => {
        const workflowActionType = this.app.$registry.get(
          'workflowAction',
          workflowAction.type
        )
        return workflowActionType.isInError(workflowAction, applicationContext)
      })

      if (hasActionInError) {
        return this.app.i18n.t('pageSidePanelType.eventsTabInError')
      }
    }

    return super.getErrorMessage(applicationContext)
  }
}
