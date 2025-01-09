import ViewFilterTypeText from '@baserow/modules/database/components/view/ViewFilterTypeText'
import ViewFilterTypeNumber from '@baserow/modules/database/components/view/ViewFilterTypeNumber'
import { FormulaFieldType } from '@baserow/modules/database/fieldTypes'
import { ViewFilterType } from '@baserow/modules/database/viewFilters'
import viewFilterTypeText from '@baserow/modules/database/components/view/ViewFilterTypeText.vue'
import ViewFilterTypeMultipleSelectOptions from '@baserow/modules/database/components/view/ViewFilterTypeMultipleSelectOptions'
import { BaserowFormulaNumberType } from '@baserow/modules/database/formula/formulaTypes'
import { ComparisonOperator } from '@baserow/modules/database//utils/fieldFilters'

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
      FormulaFieldType.compatibleWithFormulaTypes('array(number)'),
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
      FormulaFieldType.compatibleWithFormulaTypes('array(number)'),
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
    filterValue = fieldType.prepareFilterValue(field, filterValue)
    return fieldType.hasValueEqualFilter(cellValue, filterValue, field)
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
        FormulaFieldType.arrayOf('single_select'),
        FormulaFieldType.arrayOf('number')
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
    filterValue = fieldType.prepareFilterValue(field, filterValue)
    return fieldType.hasNotValueEqualFilter(cellValue, filterValue, field)
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
        FormulaFieldType.arrayOf('single_select'),
        FormulaFieldType.arrayOf('number')
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
      FormulaFieldType.compatibleWithFormulaTypes(
        FormulaFieldType.arrayOf('char'),
        FormulaFieldType.arrayOf('text'),
        FormulaFieldType.arrayOf('url'),
        FormulaFieldType.arrayOf('single_select'),
        FormulaFieldType.arrayOf('number')
      ),
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
      FormulaFieldType.compatibleWithFormulaTypes(
        FormulaFieldType.arrayOf('char'),
        FormulaFieldType.arrayOf('text'),
        FormulaFieldType.arrayOf('url'),
        FormulaFieldType.arrayOf('single_select'),
        FormulaFieldType.arrayOf('number')
      ),
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
    filterValue = fieldType.prepareFilterValue(field, filterValue)
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

export class HasValueHigherThanViewFilterType extends ViewFilterType {
  static getType() {
    return 'has_value_higher'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasValueHigherThan')
  }

  getInputComponent(field) {
    return ViewFilterTypeNumber
  }

  getCompatibleFieldTypes() {
    return [
      FormulaFieldType.compatibleWithFormulaTypes(
        FormulaFieldType.arrayOf(BaserowFormulaNumberType.getType())
      ),
    ]
  }

  matches(cellValue, filterValue, field, fieldType) {
    filterValue = fieldType.prepareFilterValue(field, filterValue)
    return (
      filterValue === '' ||
      fieldType.hasValueComparableToFilter(
        cellValue,
        filterValue,
        field,
        ComparisonOperator.HIGHER_THAN
      )
    )
  }
}

export class HasNotValueHigherThanViewFilterType extends HasValueHigherThanViewFilterType {
  static getType() {
    return 'has_not_value_higher'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasNotValueHigherThan')
  }

  matches(cellValue, filterValue, field, fieldType) {
    filterValue = fieldType.prepareFilterValue(field, filterValue)
    return (
      filterValue === '' ||
      !fieldType.hasValueComparableToFilter(
        cellValue,
        filterValue,
        field,
        ComparisonOperator.HIGHER_THAN
      )
    )
  }
}

export class HasValueHigherThanOrEqualViewFilterType extends ViewFilterType {
  static getType() {
    return 'has_value_higher_or_equal'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasValueHigherThanOrEqual')
  }

  getInputComponent(field) {
    return ViewFilterTypeNumber
  }

  getCompatibleFieldTypes() {
    return [
      FormulaFieldType.compatibleWithFormulaTypes(
        FormulaFieldType.arrayOf(BaserowFormulaNumberType.getType())
      ),
    ]
  }

  matches(cellValue, filterValue, field, fieldType) {
    filterValue = fieldType.prepareFilterValue(field, filterValue)
    return (
      filterValue === '' ||
      fieldType.hasValueComparableToFilter(
        cellValue,
        filterValue,
        field,
        ComparisonOperator.HIGHER_THAN_OR_EQUAL
      )
    )
  }
}

export class HasNotValueHigherThanOrEqualViewFilterType extends HasValueHigherThanOrEqualViewFilterType {
  static getType() {
    return 'has_not_value_higher_or_equal'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasNotValueHigherThanOrEqual')
  }

  matches(cellValue, filterValue, field, fieldType) {
    filterValue = fieldType.prepareFilterValue(field, filterValue)
    return (
      filterValue === '' ||
      !fieldType.hasValueComparableToFilter(
        cellValue,
        filterValue,
        field,
        ComparisonOperator.HIGHER_THAN_OR_EQUAL
      )
    )
  }
}

export class HasValueLowerThanViewFilterType extends ViewFilterType {
  static getType() {
    return 'has_value_lower'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasValueLowerThan')
  }

  getInputComponent(field) {
    return ViewFilterTypeNumber
  }

  getCompatibleFieldTypes() {
    return [
      FormulaFieldType.compatibleWithFormulaTypes(
        FormulaFieldType.arrayOf(BaserowFormulaNumberType.getType())
      ),
    ]
  }

  matches(cellValue, filterValue, field, fieldType) {
    filterValue = fieldType.prepareFilterValue(field, filterValue)
    return (
      filterValue === '' ||
      fieldType.hasValueComparableToFilter(
        cellValue,
        filterValue,
        field,
        ComparisonOperator.LOWER_THAN
      )
    )
  }
}

export class HasNotValueLowerThanViewFilterType extends HasValueLowerThanViewFilterType {
  static getType() {
    return 'has_not_value_lower'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasNotValueLowerThan')
  }

  matches(cellValue, filterValue, field, fieldType) {
    filterValue = fieldType.prepareFilterValue(field, filterValue)
    return (
      filterValue === '' ||
      !fieldType.hasValueComparableToFilter(
        cellValue,
        filterValue,
        field,
        ComparisonOperator.LOWER_THAN
      )
    )
  }
}

export class HasValueLowerThanOrEqualViewFilterType extends ViewFilterType {
  static getType() {
    return 'has_value_lower_or_equal'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasValueLowerThanOrEqual')
  }

  getInputComponent(field) {
    return ViewFilterTypeNumber
  }

  getCompatibleFieldTypes() {
    return [
      FormulaFieldType.compatibleWithFormulaTypes(
        FormulaFieldType.arrayOf(BaserowFormulaNumberType.getType())
      ),
    ]
  }

  matches(cellValue, filterValue, field, fieldType) {
    filterValue = fieldType.prepareFilterValue(field, filterValue)
    return (
      filterValue === '' ||
      fieldType.hasValueComparableToFilter(
        cellValue,
        filterValue,
        field,
        ComparisonOperator.LOWER_THAN_OR_EQUAL
      )
    )
  }
}

export class HasNotValueLowerThanOrEqualViewFilterType extends HasValueLowerThanOrEqualViewFilterType {
  static getType() {
    return 'has_not_value_lower_or_equal'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasNotValueLowerThanOrEqual')
  }

  matches(cellValue, filterValue, field, fieldType) {
    filterValue = fieldType.prepareFilterValue(field, filterValue)
    return (
      filterValue === '' ||
      !fieldType.hasValueComparableToFilter(
        cellValue,
        filterValue,
        field,
        ComparisonOperator.LOWER_THAN_OR_EQUAL
      )
    )
  }
}
