import { Registerable } from '@baserow/modules/core/registry'
import {
  TextFieldType,
  LongTextFieldType,
  RatingFieldType,
  NumberFieldType,
  DateFieldType,
  URLFieldType,
  EmailFieldType,
  DurationFieldType,
  SingleSelectFieldType,
} from '@baserow/modules/database/fieldTypes'
import { UNIQUE_WITH_EMPTY_CONSTRAINT_NAME } from '@baserow/modules/database/constants'

export class FieldConstraintType extends Registerable {
  /**
   * A human readable name of the field constraint type.
   */
  getName() {
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
      name: this.getTypeName(),
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
   * Returns whether this constraint can support default values.
   * If false, the default value field should be disabled when this constraint is selected.
   * @returns {boolean} True if the constraint can support default values, false otherwise.
   */
  canSupportDefaultValue() {
    return true
  }

  /**
   * Returns a map of error codes to their corresponding error messages.
   * Subclasses can override this method to provide custom error messages
   * for specific error codes.
   * @returns {Object} Object mapping error codes to error messages
   */
  getErrorMap() {
    return {
      ERROR_INVALID_FIELD_CONSTRAINT: this.$t(
        'fieldConstraintsSubform.errorInvalidConstraint'
      ),
      ERROR_FIELD_CONSTRAINT_DOES_NOT_SUPPORT_DEFAULT_VALUE: this.$t(
        'fieldConstraintsSubform.errorDoesNotSupportDefaultValue'
      ),
    }
  }

  /**
   * Returns the error message that should be displayed when the field constraint
   * cannot be applied.
   * @returns {string} The error message.
   */
  getErrorMessage(error) {
    const errorMap = this.getErrorMap()
    return (
      errorMap[error] || this.$t('fieldConstraintsSubform.errorGenericData')
    )
  }

  /**
   * Returns the name identifier for this constraint type.
   * Constraints with the same name are equivalent and can be converted between each other.
   * @returns {string|null} The name identifier, or null if this constraint has no equivalents.
   */
  getTypeName() {
    return null
  }

  /**
   * Finds the equivalent constraint type for a given field type.
   * @param {string} fieldType The field type to find an equivalent constraint for.
   * @param {object} constraintTypesRegistry The registry of all constraint types.
   * @returns {string|null} The constraint type name that is equivalent and compatible with the field type, or null if none found.
   */
  findEquivalentConstraintForFieldType(fieldType, constraintTypesRegistry) {
    const typeName = this.getTypeName()
    if (!typeName) {
      return null
    }

    for (const [constraintTypeName, constraintType] of Object.entries(
      constraintTypesRegistry
    )) {
      if (
        constraintType.getTypeName() === typeName &&
        constraintType.getCompatibleFieldTypes().includes(fieldType)
      ) {
        return constraintTypeName
      }
    }

    return null
  }
}

export class UniqueWithEmptyConstraintType extends FieldConstraintType {
  getName() {
    const { i18n } = this.app
    return i18n.t('fieldConstraint.uniqueWithEmpty')
  }

  getTypeName() {
    return UNIQUE_WITH_EMPTY_CONSTRAINT_NAME
  }

  canSupportDefaultValue() {
    return false
  }

  getErrorMap() {
    return {
      ...super.getErrorMap(),
      ERROR_FIELD_CONSTRAINT: this.$t(
        'fieldConstraintsSubform.errorUniqueOrEmpty'
      ),
    }
  }
}

export class TextTypeUniqueWithEmptyConstraintType extends UniqueWithEmptyConstraintType {
  static getType() {
    return 'text_type_unique_with_empty'
  }

  getCompatibleFieldTypes() {
    return [
      TextFieldType.getType(),
      LongTextFieldType.getType(),
      URLFieldType.getType(),
      EmailFieldType.getType(),
    ]
  }
}

export class RatingTypeUniqueWithEmptyConstraintType extends UniqueWithEmptyConstraintType {
  static getType() {
    return 'rating_type_unique_with_empty'
  }

  getCompatibleFieldTypes() {
    return [RatingFieldType.getType()]
  }
}

export class GenericUniqueWithEmptyConstraintType extends UniqueWithEmptyConstraintType {
  static getType() {
    return 'generic_unique_with_empty'
  }

  getCompatibleFieldTypes() {
    return [
      NumberFieldType.getType(),
      DateFieldType.getType(),
      DurationFieldType.getType(),
      SingleSelectFieldType.getType(),
    ]
  }
}
