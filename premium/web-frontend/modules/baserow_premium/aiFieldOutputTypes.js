import { Registerable } from '@baserow/modules/core/registry'

import {
  LongTextFieldType,
  SingleSelectFieldType,
} from '@baserow/modules/database/fieldTypes'
import FieldSelectOptionsSubForm from '@baserow/modules/database/components/field/FieldSelectOptionsSubForm.vue'
export class AIFieldOutputType extends Registerable {
  /**
   * A human readable name of the AI output type. This will be shown in in the dropdown
   * where the user chosen the type.
   */
  getName() {
    return null
  }

  /**
   * A human-readable description of the AI output type.
   */
  getDescription() {
    return null
  }

  constructor(...args) {
    super(...args)
    this.type = this.getType()

    if (this.type === null) {
      throw new Error('The type name of an admin type must be set.')
    }
    if (this.name === null) {
      throw new Error('The name of an admin type must be set.')
    }
  }

  getBaserowFieldType() {
    throw new Error('The Baserow field type must be set on the AI output type.')
  }

  /**
   * Can optionally return a form component that will be added to the `FieldForm` is
   * the output type is chosen.
   */
  getFormComponent() {
    return null
  }

  /**
   * Callback called when a new value has been generated for the field. This is needed
   * for example for the text output field to refresh the copy to use when editing.
   */
  updateValue(outputComponent, newValue) {}
}

export class TextAIFieldOutputType extends AIFieldOutputType {
  static getType() {
    return 'text'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('aiOutputType.text')
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('aiOutputType.textDescription')
  }

  getBaserowFieldType() {
    return this.app.$registry.get('field', LongTextFieldType.getType())
  }

  updateValue(outputComponent, newValue) {
    if (outputComponent.refreshCopy) {
      outputComponent.refreshCopy(newValue) // update the editing copy
    }
  }
}

export class ChoiceAIFieldOutputType extends AIFieldOutputType {
  static getType() {
    return 'choice'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('aiOutputType.choice')
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('aiOutputType.choiceDescription')
  }

  getBaserowFieldType() {
    return this.app.$registry.get('field', SingleSelectFieldType.getType())
  }

  getFormComponent() {
    return FieldSelectOptionsSubForm
  }
}
