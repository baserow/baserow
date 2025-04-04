import { Registerable } from '@baserow/modules/core/registry'

import { compile } from 'path-to-regexp'
import PublishActionModal from '@baserow/modules/builder/components/page/header/PublishActionModal'

export class PageActionType extends Registerable {
  get label() {
    return null
  }

  get icon() {
    return null
  }

  /**
   * This is the component that will be opened when the icon is clicked. Usually this
   * is either a context or a modal.
   */
  get component() {
    return 'div'
  }

  getOrder() {
    return 0
  }

  isActive() {
    return true
  }

  /**
   * By default, we will assume that the component is a context menu and will be
   * positioned next to the icon clicked on.
   */
  onClick({ component, button }) {
    component.toggle(button, 'bottom', 'left', 4)
  }

  /**
   * The props that are added to the Button component related to this action. This can
   * be used to change the type to secondary, or add an icon.
   */
  get buttonProps() {
    return {}
  }
}

export class PublishPageActionType extends PageActionType {
  static getType() {
    return 'publish'
  }

  get label() {
    return this.app.i18n.t('pageActionTypes.publish')
  }

  get icon() {
    return 'upload'
  }

  get component() {
    return PublishActionModal
  }

  onClick({ component }) {
    component.show()
  }

  isActive({ workspace, page }) {
    return this.app.$hasPermission('builder.domain.publish', page, workspace.id)
  }

  getOrder() {
    return 20
  }

  get buttonProps() {
    return { type: 'primary' }
  }
}

export class PreviewPageActionType extends PageActionType {
  static getType() {
    return 'preview'
  }

  get label() {
    return this.app.i18n.t('pageActionTypes.preview')
  }

  generatePreviewUrl(builderId, page) {
    /**
     * Responsible for generating the preview URL for a given
     * page using the page's path parameters and query string parameters.
     *
     * @param builderId   The builder application ID.
     * @param page        The Page object.
     */

    const toPath = compile(page.path, { encode: encodeURIComponent })
    const pageParams = Object.fromEntries(
      page.path_params.map(({ name, value }) => [name, page.parameters[name]])
    )
    const resolvedPagePath = toPath(pageParams)
    const url = new URL(
      `/builder/${builderId}/preview${resolvedPagePath}`,
      window.location.origin
    )
    if (page.query_params && Array.isArray(page.query_params)) {
      page.query_params.forEach(({ name }) => {
        if (page.parameters[name]) {
          url.searchParams.append(name, page.parameters[name])
        }
      })
    }
    return url.toString()
  }

  isActive({ workspace, page }) {
    return this.app.$hasPermission('builder.domain.publish', page, workspace.id)
  }

  onClick({ builder, page }) {
    const pageUrl = this.generatePreviewUrl(builder.id, page)
    window.open(pageUrl, '_blank')
  }

  getOrder() {
    return 10
  }

  get buttonProps() {
    return { type: 'secondary', icon: 'iconoir-play' }
  }
}
