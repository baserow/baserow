import ViewFilterTypeText from '@baserow/modules/database/components/view/ViewFilterTypeText'
import ViewFilterTypeNumber from '@baserow/modules/database/components/view/ViewFilterTypeNumber'
import { FormulaFieldType } from '@baserow/modules/database/fieldTypes'
import { ViewFilterType } from '@baserow/modules/database/viewFilters'
import viewFilterTypeText from '@baserow/modules/database/components/view/ViewFilterTypeText.vue'
import ViewFilterTypeMultipleSelectOptions from '@baserow/modules/database/components/view/ViewFilterTypeMultipleSelectOptions'
import _ from 'lodash'

/**
 * This function normalizes boolean values that may be used internally in the filter
 * to values that can be transferred to the backend.
 * @param value
 * @returns {string|*}
 */
const normalizeBooleanForFilters = (value) => {
  if (!_.isBoolean(value)) {
    return value
  }
  return value ? '1' : '0'
}

export class HasEmptyValueViewFilterType extends ViewFilterType {
  static getType() {
    return 'has_empty_value'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasEmptyValue')
  }

  getCompatibleFieldTypes() {
    return [
      FormulaFieldType.compatibleWithFormulaTypes('array(text)'),
      FormulaFieldType.compatibleWithFormulaTypes('array(char)'),
      FormulaFieldType.compatibleWithFormulaTypes('array(url)'),
      FormulaFieldType.compatibleWithFormulaTypes('array(single_select)'),
    ]
  }

  matches(cellValue, filterValue, field, fieldType) {
    return fieldType.getHasEmptyValueFilterFunction(field)(cellValue)
  }
}

export class HasNotEmptyValueViewFilterType extends ViewFilterType {
  static getType() {
    return 'has_not_empty_value'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasNotEmptyValue')
  }

  getCompatibleFieldTypes() {
    return [
      FormulaFieldType.compatibleWithFormulaTypes('array(text)'),
      FormulaFieldType.compatibleWithFormulaTypes('array(char)'),
      FormulaFieldType.compatibleWithFormulaTypes('array(url)'),
      FormulaFieldType.compatibleWithFormulaTypes('array(single_select)'),
    ]
  }

  matches(cellValue, filterValue, field, fieldType) {
    return !fieldType.getHasEmptyValueFilterFunction(field)(cellValue)
  }
}

export class HasValueEqualViewFilterType extends ViewFilterType {
  static getType() {
    return 'has_value_equal'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasValueEqual')
  }

  getDefaultValue(field) {
    // has_value_equal filter by default sends an empty string. For consistency
    // a default value should be in pair with a default value from the input component.
    return this.prepareValue('', field)
  }

  matches(cellValue, filterValue, field, fieldType) {
    filterValue = fieldType.parseInputValue(field, filterValue)
    return fieldType.hasValueEqualFilter(cellValue, filterValue, field)
  }

  prepareValue(value, field) {
    const fieldType = this.app.$registry.get('field', field.type)
    return normalizeBooleanForFilters(fieldType.parseInputValue(field, value))
  }

  getInputComponent(field) {
    const fieldType = this.app.$registry.get('field', field.type)
    return fieldType.getFilterInputComponent(field, this) || viewFilterTypeText
  }

  getCompatibleFieldTypes() {
    return [
      FormulaFieldType.compatibleWithFormulaTypes(
        FormulaFieldType.arrayOf('text'),
        FormulaFieldType.arrayOf('char'),
        FormulaFieldType.arrayOf('url'),
        FormulaFieldType.arrayOf('boolean'),
        FormulaFieldType.arrayOf('single_select')
      ),
    ]
  }
}

export class HasNotValueEqualViewFilterType extends ViewFilterType {
  static getType() {
    return 'has_not_value_equal'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasNotValueEqual')
  }

  matches(cellValue, filterValue, field, fieldType) {
    filterValue = fieldType.parseInputValue(field, filterValue)
    return fieldType.hasNotValueEqualFilter(cellValue, filterValue, field)
  }

  getDefaultValue(field) {
    // has_not_value_equal filter by default sends an empty string. For consistency
    // a default value should be in pair with a default value from the input component.
    return this.prepareValue('', field)
  }

  prepareValue(value, field) {
    const fieldType = this.app.$registry.get('field', field.type)
    return normalizeBooleanForFilters(fieldType.parseInputValue(field, value))
  }

  getInputComponent(field) {
    const fieldType = this.app.$registry.get('field', field.type)
    return fieldType.getFilterInputComponent(field, this) || viewFilterTypeText
  }

  getCompatibleFieldTypes() {
    return [
      FormulaFieldType.compatibleWithFormulaTypes(
        FormulaFieldType.arrayOf('text'),
        FormulaFieldType.arrayOf('char'),
        FormulaFieldType.arrayOf('url'),
        FormulaFieldType.arrayOf('boolean'),
        FormulaFieldType.arrayOf('single_select')
      ),
    ]
  }
}

export class HasValueContainsViewFilterType extends ViewFilterType {
  static getType() {
    return 'has_value_contains'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasValueContains')
  }

  getInputComponent(field) {
    return ViewFilterTypeText
  }

  getCompatibleFieldTypes() {
    return [
      FormulaFieldType.compatibleWithFormulaTypes('array(text)'),
      FormulaFieldType.compatibleWithFormulaTypes('array(char)'),
      FormulaFieldType.compatibleWithFormulaTypes('array(url)'),
      FormulaFieldType.compatibleWithFormulaTypes('array(single_select)'),
    ]
  }

  matches(cellValue, filterValue, field, fieldType) {
    return fieldType.hasValueContainsFilter(cellValue, filterValue, field)
  }
}

export class HasNotValueContainsViewFilterType extends ViewFilterType {
  static getType() {
    return 'has_not_value_contains'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasNotValueContains')
  }

  getInputComponent(field) {
    return ViewFilterTypeText
  }

  getCompatibleFieldTypes() {
    return [
      FormulaFieldType.compatibleWithFormulaTypes('array(text)'),
      FormulaFieldType.compatibleWithFormulaTypes('array(char)'),
      FormulaFieldType.compatibleWithFormulaTypes('array(url)'),
      FormulaFieldType.compatibleWithFormulaTypes('array(single_select)'),
    ]
  }

  matches(cellValue, filterValue, field, fieldType) {
    return fieldType.hasNotValueContainsFilter(cellValue, filterValue, field)
  }
}

export class HasValueContainsWordViewFilterType extends ViewFilterType {
  static getType() {
    return 'has_value_contains_word'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasValueContainsWord')
  }

  getInputComponent(field) {
    return ViewFilterTypeText
  }

  getCompatibleFieldTypes() {
    return [
      FormulaFieldType.compatibleWithFormulaTypes('array(text)'),
      FormulaFieldType.compatibleWithFormulaTypes('array(char)'),
      FormulaFieldType.compatibleWithFormulaTypes('array(url)'),
      FormulaFieldType.compatibleWithFormulaTypes('array(single_select)'),
    ]
  }

  matches(cellValue, filterValue, field, fieldType) {
    return fieldType.hasValueContainsWordFilter(cellValue, filterValue, field)
  }
}

export class HasNotValueContainsWordViewFilterType extends ViewFilterType {
  static getType() {
    return 'has_not_value_contains_word'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasNotValueContainsWord')
  }

  getInputComponent(field) {
    return ViewFilterTypeText
  }

  getCompatibleFieldTypes() {
    return [
      FormulaFieldType.compatibleWithFormulaTypes('array(text)'),
      FormulaFieldType.compatibleWithFormulaTypes('array(char)'),
      FormulaFieldType.compatibleWithFormulaTypes('array(url)'),
      FormulaFieldType.compatibleWithFormulaTypes('array(single_select)'),
    ]
  }

  matches(cellValue, filterValue, field, fieldType) {
    return fieldType.hasNotValueContainsWordFilter(
      cellValue,
      filterValue,
      field
    )
  }
}

export class HasValueLengthIsLowerThanViewFilterType extends ViewFilterType {
  static getType() {
    return 'has_value_length_is_lower_than'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasValueLengthIsLowerThan')
  }

  getInputComponent(field) {
    return ViewFilterTypeNumber
  }

  getCompatibleFieldTypes() {
    return [
      FormulaFieldType.compatibleWithFormulaTypes('array(text)'),
      FormulaFieldType.compatibleWithFormulaTypes('array(char)'),
      FormulaFieldType.compatibleWithFormulaTypes('array(url)'),
    ]
  }

  matches(cellValue, filterValue, field, fieldType) {
    return fieldType.getHasValueLengthIsLowerThanFilterFunction(field)(
      cellValue,
      filterValue
    )
  }
}

export class HasAllValuesEqualViewFilterType extends ViewFilterType {
  static getType() {
    return 'has_all_values_equal'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasAllValuesEqual')
  }

  getInputComponent(field) {
    const fieldType = this.app.$registry.get('field', field.type)
    return fieldType.getFilterInputComponent(field, this) || viewFilterTypeText
  }

  getCompatibleFieldTypes() {
    return [FormulaFieldType.compatibleWithFormulaTypes('array(boolean)')]
  }

  matches(cellValue, filterValue, field, fieldType) {
    filterValue = fieldType.parseInputValue(field, filterValue)
    return fieldType.hasAllValuesEqualFilter(cellValue, filterValue, field)
  }
}

export class HasAnySelectOptionEqualViewFilterType extends ViewFilterType {
  static getType() {
    return 'has_any_select_option_equal'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasAnySelectOptionEqual')
  }

  getInputComponent(field) {
    return ViewFilterTypeMultipleSelectOptions
  }

  getCompatibleFieldTypes() {
    return [FormulaFieldType.compatibleWithFormulaTypes('array(single_select)')]
  }

  matches(cellValue, filterValue, field, fieldType) {
    return fieldType.hasValueEqualFilter(cellValue, filterValue, field)
  }
}

export class HasNoneSelectOptionEqualViewFilterType extends ViewFilterType {
  static getType() {
    return 'has_none_select_option_equal'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasNoneSelectOptionEqual')
  }

  getInputComponent(field) {
    return ViewFilterTypeMultipleSelectOptions
  }

  getCompatibleFieldTypes() {
    return [FormulaFieldType.compatibleWithFormulaTypes('array(single_select)')]
  }

  matches(cellValue, filterValue, field, fieldType) {
    return fieldType.hasNotValueEqualFilter(cellValue, filterValue, field)
  }
}
