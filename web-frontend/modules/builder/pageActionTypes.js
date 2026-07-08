import { Registerable } from '@baserow/modules/core/registry'

import { compile } from 'path-to-regexp'
import PublishActionModal from '@baserow/modules/builder/components/page/header/PublishActionModal'
import { ensureString } from '@baserow/modules/core/utils/validator'
import PublishedBuilderService from '@baserow/modules/builder/services/publishedBuilder'
import { normalizePreviewPathPrefix } from '@baserow/modules/builder/utils/urlResolution'

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
    return this.app.$i18n.t('pageActionTypes.publish')
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
    return this.app.$i18n.t('pageActionTypes.preview')
  }

  generatePreviewPath(page) {
    /**
     * Responsible for generating the preview path for a given
     * page using the page's path parameters and query string parameters.
     *
     * @param page        The Page object.
     */

    const toPath = compile(page.path, { encode: encodeURIComponent })
    const pageParams = Object.fromEntries(
      page.path_params.map(({ name }) => [
        name,
        ensureString(page.parameters[name]), // toPath needs strings
      ])
    )

    const resolvedPagePath = toPath(pageParams)

    const url = new URL(resolvedPagePath, 'http://preview.local')
    if (page.query_params && Array.isArray(page.query_params)) {
      page.query_params.forEach(({ name }) => {
        if (page.parameters[name]) {
          url.searchParams.append(name, page.parameters[name])
        }
      })
    }
    return `${url.pathname}${url.search}`
  }

  generatePreviewUrl(page) {
    const previewPathPrefix = normalizePreviewPathPrefix(
      this.app.$config.public.builderPreviewPathPrefix
    )
    const url = new URL(
      `${previewPathPrefix}${this.generatePreviewPath(page)}`,
      this.app.$config.public.builderPreviewUrl
    )
    return url.toString()
  }

  isActive({ workspace, page }) {
    return this.app.$hasPermission('builder.domain.publish', page, workspace.id)
  }

  async onClick({ builder, page }) {
    const { data } = await PublishedBuilderService(
      this.app.$client
    ).createPreviewGrant(builder.id, this.generatePreviewPath(page))
    window.open(data.url, '_blank')
  }

  getOrder() {
    return 10
  }

  get buttonProps() {
    return { type: 'secondary', icon: 'iconoir-play' }
  }
}
