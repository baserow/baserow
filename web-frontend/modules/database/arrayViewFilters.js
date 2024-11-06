import ViewFilterTypeText from '@baserow/modules/database/components/view/ViewFilterTypeText'
import ViewFilterTypeNumber from '@baserow/modules/database/components/view/ViewFilterTypeNumber'
import { FormulaFieldType } from '@baserow/modules/database/fieldTypes'
import { ViewFilterType } from '@baserow/modules/database/viewFilters'
import viewFilterTypeText from '@baserow/modules/database/components/view/ViewFilterTypeText.vue'

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

  matches(cellValue, filterValue, field, fieldType) {
    filterValue = fieldType.parseInputValue(field, filterValue)
    return fieldType.hasValueEqualFilter(cellValue, filterValue, field)
  }

  getInputComponent(field) {
    const fieldType = this.$app.registry.get('field_type', field.type)
    return fieldType.getFilterInputComponent(field, this) || viewFilterTypeText
  }

  getCompatibleFieldTypes() {
    return [
      FormulaFieldType.compatibleWithFormulaTypes(
        FormulaFieldType.arrayOf('text'),
        FormulaFieldType.arrayOf('char'),
        FormulaFieldType.arrayOf('url'),
        FormulaFieldType.arrayOf('boolean')
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

  getInputComponent(field) {
    const fieldType = this.$app.registry.get('field_type', field.type)
    return fieldType.getFilterInputComponent(field, this) || viewFilterTypeText
  }

  getCompatibleFieldTypes() {
    return [
      FormulaFieldType.compatibleWithFormulaTypes(
        FormulaFieldType.arrayOf('text'),
        FormulaFieldType.arrayOf('char'),
        FormulaFieldType.arrayOf('url'),
        FormulaFieldType.arrayOf('boolean')
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
    const fieldType = this.$app.registry.get('field_type', field.type)
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
