import { Registerable } from '@baserow/modules/core/registry'

/**
 * Adds a setting to the advanced tab of the field form. The component is a child
 * form, so its values are sent together with the other field values.
 */
export class FieldFormAdvancedSettingType extends Registerable {
  get component() {
    throw new Error(
      'component getter must be implemented in the FieldFormAdvancedSettingType.'
    )
  }
}
