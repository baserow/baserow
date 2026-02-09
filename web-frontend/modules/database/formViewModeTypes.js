import { Registerable } from '@baserow/modules/core/registry'

import FormViewModePreviewForm from '@baserow/modules/database/components/view/form/FormViewModePreviewForm'
import FormViewModeForm from '@baserow/modules/database/components/view/form/FormViewModeForm'

export class FormViewModeType extends Registerable {
  constructor(...args) {
    super(...args)
    this.type = this.getType()

    if (this.type === null) {
      throw new Error('The type name of a form mode type must be set.')
    }
  }

  /**
   * A human readable name of the decorator type.
   */
  getName() {
    return null
  }

  /**
   * A description of the decorator type.
   */
  getDescription() {
    return null
  }

  /**
   * Should return a icon class name class name related to the icon that must be displayed
   * to the user.
   */
  getIconClass() {
    throw new Error('The icon class of an importer type must be set.')
  }

  /**
   * If the decorator type is disabled, this text will be visible explaining why.
   */
  getDeactivatedText({ view }) {}

  /**
   * When the deactivated view decorator is clicked, this modal will be shown.
   */
  getDeactivatedClickModal() {
    return null
  }

  /**
   * Indicates if the decorator type is disabled.
   */
  isDeactivated(workspaceId) {
    return false
  }

  /**
   * This is the component that's responsible for previewing and editing the form.
   * It will be shown to users who who want to edit the form.
   */
  getPreviewComponent() {
    throw new Error('The form mode preview component must returned.')
  }

  /**
   * This is the component that's responsible where public visitors can fill out the
   * form after it has been shared publicly.
   */
  getFormComponent() {
    throw new Error('The form mode component must be returned.')
  }
}

export class FormViewFormModeType extends FormViewModeType {
  static getType() {
    return 'form'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('formViewModeType.form')
  }

  getDescription() {
    const { $i18n: i18n } = this.app
    return i18n.t('formViewModeType.formDescription')
  }

  getIconClass() {
    return 'iconoir-page'
  }

  getPreviewComponent() {
    return FormViewModePreviewForm
  }

  getFormComponent() {
    return FormViewModeForm
  }
}
