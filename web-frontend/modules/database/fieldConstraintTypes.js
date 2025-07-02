import { Registerable } from '@baserow/modules/core/registry'

export class FieldConstraintType extends Registerable {
  /**
   * A human readable label of the field constraint type.
   */
  getLabel() {
    return null
  }

  constructor(...args) {
    super(...args)
    this.type = this.getType()
    this.compatibleFieldTypes = this.getCompatibleFieldTypes()

    if (this.type === null) {
      throw new Error('The type name of a field constraint type must be set.')
    }
    if (this.name === null) {
      throw new Error('The name of a field constraint type must be set.')
    }
  }

  /**
   * @return object
   */
  serialize() {
    return {
      type: this.type,
      name: this.getName(),
      compatibleFieldTypes: this.compatibleFieldTypes,
    }
  }

  /**
   * Should return a component that is responsible for the field constraint's parameters.
   * For example for the min/max length constraint a text field will be added where
   * the user can enter the min/max length.
   */
  getParametersComponent() {
    return null
  }

  /**
   * Should return the field type names that the field constraint is compatible with
   */
  getCompatibleFieldTypes() {
    return []
  }

  /**
   * Returns if a given field is compatible with this field constraint or not. Uses the
   * list provided by getCompatibleFieldTypes to calculate this.
   */
  fieldIsCompatible(field) {
    const valuesMap = this.getCompatibleFieldTypes().map((type) => [type, true])
    return this.getCompatibleFieldValue(field, valuesMap, false)
  }

  /**
   * Given a field and a map of field types to values, this method will return the
   * value that is compatible with the field. If no value is found the notFoundValue
   * will be returned.
   * This can be used to verify if a field is compatible with a field constraint type or to
   * return the correct component for the field constraint input.
   * @param {object} field The field object that should be checked.
   * @param {object} valuesMap A list of tuple where the key is the field type and the value is the value that should be
   * returned if the field is compatible.
   * @param {any} notFoundValue The value that should be returned if no compatible value is found.
   * @returns {any} The value that is compatible with the field or the notFoundValue.
   */
  getCompatibleFieldValue(field, valuesMap, notFoundValue = null) {
    for (const [type, value] of valuesMap) {
      if (field.type === type) {
        return value
      }
    }
    return notFoundValue
  }

  /**
   * Returns the error message that should be displayed when the field constraint
   * cannot be applied.
   * @returns {string} The error message.
   */
  getErrorMessage(error) {
    if (error === 'ERROR_INVALID_FIELD_CONSTRAINT') {
      return this.$t('fieldConstraintsSubform.errorInvalidConstraint')
    }

    return this.$t('fieldConstraintsSubform.errorGenericData')
  }

  /**
   * Returns the name identifier for this constraint type.
   * Constraints with the same name are equivalent and can be converted between each other.
   * @returns {string|null} The name identifier, or null if this constraint has no equivalents.
   */
  getName() {
    return null
  }

  /**
   * Finds the equivalent constraint type for a given field type.
   * @param {string} fieldType The field type to find an equivalent constraint for.
   * @param {object} constraintTypesRegistry The registry of all constraint types.
   * @returns {string|null} The constraint type name that is equivalent and compatible with the field type, or null if none found.
   */
  findEquivalentConstraintForFieldType(fieldType, constraintTypesRegistry) {
    const name = this.getName()
    if (!name) {
      return null
    }

    for (const [constraintTypeName, constraintType] of Object.entries(
      constraintTypesRegistry
    )) {
      if (
        constraintType.getName() === name &&
        constraintType.getCompatibleFieldTypes().includes(fieldType)
      ) {
        console.log('found', constraintTypeName)
        return constraintTypeName
      }
    }

    return null
  }
}

export class TextTypeUniqueWithEmptyConstraintType extends FieldConstraintType {
  static getType() {
    return 'text_type_unique_with_empty'
  }

  getLabel() {
    const { i18n } = this.app
    return i18n.t('fieldConstraint.uniqueWithEmpty')
  }

  getCompatibleFieldTypes() {
    return ['text', 'long_text']
  }

  getName() {
    return 'unique_with_empty'
  }

  getErrorMessage(error) {
    if (error === 'ERROR_FIELD_CONSTRAINT') {
      return this.$t('fieldConstraintsSubform.errorUniqueOrEmpty')
    }

    return super.getErrorMessage(error)
  }
}

export class RatingTypeUniqueWithEmptyConstraintType extends FieldConstraintType {
  static getType() {
    return 'rating_type_unique_with_empty'
  }

  getLabel() {
    const { i18n } = this.app
    return i18n.t('fieldConstraint.uniqueWithEmpty')
  }

  getCompatibleFieldTypes() {
    return ['rating']
  }

  getName() {
    return 'unique_with_empty'
  }

  getErrorMessage(error) {
    if (error === 'ERROR_FIELD_CONSTRAINT') {
      return this.$t('fieldConstraintsSubform.errorUniqueOrEmpty')
    }

    return super.getErrorMessage(error)
  }
}

export class UniqueWithEmptyConstraintType extends FieldConstraintType {
  static getType() {
    return 'unique_with_empty'
  }

  getLabel() {
    const { i18n } = this.app
    return i18n.t('fieldConstraint.uniqueWithEmpty')
  }

  getCompatibleFieldTypes() {
    return ['number']
  }

  getName() {
    return 'unique_with_empty'
  }

  getErrorMessage(error) {
    if (error === 'ERROR_FIELD_CONSTRAINT') {
      return this.$t('fieldConstraintsSubform.errorUniqueOrEmpty')
    }

    return super.getErrorMessage(error)
  }
}
