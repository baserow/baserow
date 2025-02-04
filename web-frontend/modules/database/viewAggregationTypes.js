import { Registerable } from '@baserow/modules/core/registry'
import GenericViewAggregation from '@baserow/modules/database/components/aggregation/GenericViewAggregation'
import DistributionAggregation from '@baserow/modules/database/components/aggregation/DistributionAggregation'
import { FormulaFieldType } from '@baserow/modules/database/fieldTypes'

export class ViewAggregationType extends Registerable {
  /**
   * A human readable name of the aggregation type.
   */
  getName() {
    return null
  }

  /**
   * A human readable name of the aggregation type to display in the menu.
   */
  getShortName() {
    return this.getName()
  }

  /**
   * Returns the raw aggregation type which is used by the backend to compute the
   * aggregation.
   */
  getRawType() {
    return this.getType()
  }

  /**
   * Should return the field type names that the aggregation is compatible with or
   * functions which take a field and return a boolean indicating if the field is
   * compatible or not.
   *
   * So for example ['text', 'long_text']. You can create this type of aggregation
   * only for `text` and `long_text` field type.
   *
   * Or using a function you could do [(field) => field.some_prop === 10, 'long_text']
   * and then fields which pass the test defined by the function will be deemed as
   * compatible.
   *
   */
  getCompatibleFieldTypes() {
    return []
  }

  /**
   * Returns if a given field is compatible with this view aggregation or not.
   * Uses the list provided by getCompatibleFieldTypes to calculate this.
   */
  fieldIsCompatible(field) {
    for (const typeOrFunc of this.getCompatibleFieldTypes()) {
      if (typeOrFunc instanceof Function) {
        if (typeOrFunc(field)) {
          return true
        }
      } else if (field.type === typeOrFunc) {
        return true
      }
    }
    return false
  }

  /**
   * Should return the component that will actually display the aggregation.
   */
  getComponent() {
    throw new Error(
      'Not implemented error. This aggregation should return a component.'
    )
  }

  getOrder() {
    return 50
  }

  formatValue(value, context) {
    if (isNaN(value)) {
      return null
    }
    return value
  }

  /**
   * Compute the final aggregation value from the value sent by the server and the given
   * context.
   * @param {*} value is the value from the backend.
   * @param {object} context is an object containing data to describe the context of the
   *    aggregation.
   * @returns the final aggregation value for this type.
   */
  getValue(value, context) {
    return this.formatValue(value, context)
  }

  isAllowedInView() {
    return true
  }

  /**
   * @return object
   */
  serialize() {
    return {
      type: this.type,
      rawType: this.getRawType(),
      name: this.getName(),
    }
  }
}

export class CountViewAggregationType extends ViewAggregationType {
  static getType() {
    return 'count'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.count')
  }

  getCompatibleFieldTypes() {
    return [
      'text',
      'long_text',
      'boolean',
      'url',
      'email',
      'number',
      'date',
      'last_modified',
      'last_modified_by',
      'created_on',
      'created_by',
      'link_row',
      'file',
      'single_select',
      'multiple_select',
      'phone_number',
      'duration',
      'password',
      FormulaFieldType.compatibleWithFormulaTypes(
        'text',
        'char',
        'date',
        'number',
        'boolean',
        FormulaFieldType.arrayOf('single_file')
      ),
    ]
  }

  getComponent() {
    return GenericViewAggregation
  }

  isAllowedInView() {
    return false
  }
}

export class EmptyCountViewAggregationType extends ViewAggregationType {
  static getType() {
    return 'empty_count'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.emptyCount')
  }

  getCompatibleFieldTypes() {
    return [
      'text',
      'long_text',
      'url',
      'email',
      'number',
      'date',
      'last_modified',
      'last_modified_by',
      'created_on',
      'created_by',
      'link_row',
      'file',
      'single_select',
      'multiple_select',
      'phone_number',
      'duration',
      'password',
      FormulaFieldType.compatibleWithFormulaTypes(
        'text',
        'char',
        'date',
        'number',
        FormulaFieldType.arrayOf('single_file')
      ),
    ]
  }

  getComponent() {
    return GenericViewAggregation
  }
}

export class NotEmptyCountViewAggregationType extends ViewAggregationType {
  static getType() {
    return 'not_empty_count'
  }

  getRawType() {
    return 'empty_count'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.notEmptyCount')
  }

  getCompatibleFieldTypes() {
    return [
      'text',
      'long_text',
      'url',
      'email',
      'number',
      'date',
      'last_modified',
      'created_on',
      'link_row',
      'file',
      'single_select',
      'multiple_select',
      'phone_number',
      'duration',
      'password',
      FormulaFieldType.compatibleWithFormulaTypes(
        'text',
        'char',
        'date',
        'number',
        FormulaFieldType.arrayOf('single_file')
      ),
    ]
  }

  getValue(value, { rowCount }) {
    if (rowCount === 0 || isNaN(value)) {
      return null
    }
    return this.formatValue(rowCount - value)
  }

  getComponent() {
    return GenericViewAggregation
  }
}

export class NotCheckedCountViewAggregationType extends ViewAggregationType {
  static getType() {
    return 'not_checked_count'
  }

  getRawType() {
    return 'empty_count'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.notCheckedCount')
  }

  getCompatibleFieldTypes() {
    return ['boolean', FormulaFieldType.compatibleWithFormulaTypes('boolean')]
  }

  getComponent() {
    return GenericViewAggregation
  }
}

export class CheckedCountViewAggregationType extends ViewAggregationType {
  static getType() {
    return 'checked_count'
  }

  getRawType() {
    return 'empty_count'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.checkedCount')
  }

  getCompatibleFieldTypes() {
    return ['boolean', FormulaFieldType.compatibleWithFormulaTypes('boolean')]
  }

  getValue(value, { rowCount }) {
    if (rowCount === 0 || isNaN(value)) {
      return null
    }
    return this.formatValue(rowCount - value)
  }

  getComponent() {
    return GenericViewAggregation
  }
}

export class EmptyPercentageViewAggregationType extends ViewAggregationType {
  static getType() {
    return 'empty_percentage'
  }

  getRawType() {
    return 'empty_count'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.emptyPercentage')
  }

  getShortName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.emptyCount')
  }

  getCompatibleFieldTypes() {
    return [
      'text',
      'long_text',
      'url',
      'email',
      'number',
      'date',
      'last_modified',
      'last_modified_by',
      'created_on',
      'created_by',
      'link_row',
      'file',
      'single_select',
      'multiple_select',
      'phone_number',
      'duration',
      'password',
      FormulaFieldType.compatibleWithFormulaTypes(
        'text',
        'char',
        'date',
        'number',
        FormulaFieldType.arrayOf('single_file')
      ),
    ]
  }

  formatValue(value, context) {
    if (isNaN(value)) {
      return null
    }
    return `${Math.round(value)}%`
  }

  getValue(value, { rowCount }) {
    if (rowCount === 0 || isNaN(value)) {
      return null
    }
    return this.formatValue((value / rowCount) * 100)
  }

  getComponent() {
    return GenericViewAggregation
  }
}

export class NotEmptyPercentageViewAggregationType extends ViewAggregationType {
  static getType() {
    return 'not_empty_percentage'
  }

  getRawType() {
    return 'empty_count'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.notEmptyPercentage')
  }

  getShortName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.notEmptyCount')
  }

  getCompatibleFieldTypes() {
    return [
      'text',
      'long_text',
      'url',
      'email',
      'number',
      'date',
      'last_modified',
      'last_modified_by',
      'created_on',
      'created_by',
      'link_row',
      'file',
      'single_select',
      'multiple_select',
      'phone_number',
      'duration',
      'password',
      FormulaFieldType.compatibleWithFormulaTypes(
        'text',
        'char',
        'date',
        'number',
        FormulaFieldType.arrayOf('single_file')
      ),
    ]
  }

  formatValue(value, context) {
    if (isNaN(value)) {
      return null
    }
    return `${Math.round(value)}%`
  }

  getValue(value, { rowCount }) {
    if (rowCount === 0 || isNaN(value)) {
      return null
    }
    return this.formatValue(((rowCount - value) / rowCount) * 100)
  }

  getComponent() {
    return GenericViewAggregation
  }
}

export class NotCheckedPercentageViewAggregationType extends ViewAggregationType {
  static getType() {
    return 'not_checked_percentage'
  }

  getRawType() {
    return 'empty_count'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.notCheckedPercentage')
  }

  getShortName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.notCheckedCount')
  }

  getCompatibleFieldTypes() {
    return ['boolean', FormulaFieldType.compatibleWithFormulaTypes('boolean')]
  }

  formatValue(value, context) {
    if (isNaN(value)) {
      return null
    }
    return `${Math.round(value)}%`
  }

  getValue(value, { rowCount }) {
    if (rowCount === 0 || isNaN(value)) {
      return null
    }
    return this.formatValue((value / rowCount) * 100)
  }

  getComponent() {
    return GenericViewAggregation
  }
}

export class CheckedPercentageViewAggregationType extends ViewAggregationType {
  static getType() {
    return 'checked_percentage'
  }

  getRawType() {
    return 'empty_count'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.checkedPercentage')
  }

  getShortName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.checkedCount')
  }

  getCompatibleFieldTypes() {
    return ['boolean', FormulaFieldType.compatibleWithFormulaTypes('boolean')]
  }

  formatValue(value, context) {
    if (isNaN(value)) {
      return null
    }
    return `${Math.round(value)}%`
  }

  getValue(value, { rowCount }) {
    if (rowCount === 0 || isNaN(value)) {
      return null
    }
    return this.formatValue(((rowCount - value) / rowCount) * 100)
  }

  getComponent() {
    return GenericViewAggregation
  }
}

export class UniqueCountViewAggregationType extends ViewAggregationType {
  static getType() {
    return 'unique_count'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.uniqueCount')
  }

  getCompatibleFieldTypes() {
    return [
      'text',
      'long_text',
      'url',
      'email',
      'number',
      'date',
      'single_select',
      'phone_number',
      'duration',
      'last_modified_by',
      'created_by',
      FormulaFieldType.compatibleWithFormulaTypes(
        'text',
        'char',
        'date',
        'number'
      ),
    ]
  }

  getComponent() {
    return GenericViewAggregation
  }
}

export class MinViewAggregationType extends ViewAggregationType {
  static getType() {
    return 'min'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.min')
  }

  getCompatibleFieldTypes() {
    return [
      'autonumber',
      'number',
      'rating',
      'duration',
      FormulaFieldType.compatibleWithFormulaTypes('number'),
    ]
  }

  getComponent() {
    return GenericViewAggregation
  }

  formatValue(value, { field, fieldType }) {
    if (isNaN(value) || value === null) {
      return null
    }
    return fieldType.toHumanReadableString(field, value)
  }
}

export class MaxViewAggregationType extends ViewAggregationType {
  static getType() {
    return 'max'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.max')
  }

  getCompatibleFieldTypes() {
    return [
      'autonumber',
      'number',
      'rating',
      'duration',
      FormulaFieldType.compatibleWithFormulaTypes('number'),
    ]
  }

  getComponent() {
    return GenericViewAggregation
  }

  formatValue(value, { field, fieldType }) {
    if (isNaN(value) || value === null) {
      return null
    }
    return fieldType.toHumanReadableString(field, value)
  }
}

export class EarliestDateViewAggregationType extends ViewAggregationType {
  static getType() {
    return 'min_date'
  }

  getRawType() {
    return 'min'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.earliestDate')
  }

  getShortName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.earliestDateShort')
  }

  getCompatibleFieldTypes() {
    return [
      'date',
      'last_modified',
      'created_on',
      FormulaFieldType.compatibleWithFormulaTypes('date'),
    ]
  }

  formatValue(value, { field, fieldType }) {
    if (!(typeof value === 'string')) {
      return null
    }
    return fieldType.toHumanReadableString(field, value)
  }

  getComponent() {
    return GenericViewAggregation
  }
}

export class LatestDateViewAggregationType extends ViewAggregationType {
  static getType() {
    return 'max_date'
  }

  getRawType() {
    return 'max'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.latestDate')
  }

  getShortName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.latestDateShort')
  }

  getCompatibleFieldTypes() {
    return [
      'date',
      'last_modified',
      'created_on',
      FormulaFieldType.compatibleWithFormulaTypes('date'),
    ]
  }

  formatValue(value, { field, fieldType }) {
    if (!(typeof value === 'string')) {
      return null
    }
    return fieldType.toHumanReadableString(field, value)
  }

  getComponent() {
    return GenericViewAggregation
  }
}

export class SumViewAggregationType extends ViewAggregationType {
  static getType() {
    return 'sum'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.sum')
  }

  getCompatibleFieldTypes() {
    return [
      'number',
      'rating',
      'duration',
      FormulaFieldType.compatibleWithFormulaTypes('number'),
    ]
  }

  getComponent() {
    return GenericViewAggregation
  }

  formatValue(value, { field, fieldType }) {
    if (isNaN(value) || value === null) {
      return null
    }
    return fieldType.toHumanReadableString(field, value)
  }
}
export class AverageViewAggregationType extends ViewAggregationType {
  static getType() {
    return 'average'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.average')
  }

  getCompatibleFieldTypes() {
    return [
      'number',
      'rating',
      FormulaFieldType.compatibleWithFormulaTypes('number'),
    ]
  }

  formatValue(value, { field, fieldType }) {
    if (isNaN(value)) {
      return null
    }
    return fieldType.toHumanReadableString(field, value)
  }

  getComponent() {
    return GenericViewAggregation
  }
}

export class StdDevViewAggregationType extends ViewAggregationType {
  static getType() {
    return 'std_dev'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.stdDev')
  }

  getShortName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.stdDevShort')
  }

  getCompatibleFieldTypes() {
    return [
      'number',
      'rating',
      FormulaFieldType.compatibleWithFormulaTypes('number'),
    ]
  }

  formatValue(value, { field, fieldType }) {
    if (isNaN(value)) {
      return null
    }
    return fieldType.toHumanReadableString(field, value)
  }

  getComponent() {
    return GenericViewAggregation
  }
}

export class VarianceViewAggregationType extends ViewAggregationType {
  static getType() {
    return 'variance'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.variance')
  }

  getCompatibleFieldTypes() {
    return [
      'number',
      'rating',
      FormulaFieldType.compatibleWithFormulaTypes('number'),
    ]
  }

  formatValue(value, { field, fieldType }) {
    if (isNaN(value)) {
      return null
    }
    return fieldType.toHumanReadableString(field, value)
  }

  getComponent() {
    return GenericViewAggregation
  }
}

export class MedianViewAggregationType extends ViewAggregationType {
  static getType() {
    return 'median'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.median')
  }

  getCompatibleFieldTypes() {
    return [
      'number',
      'rating',
      FormulaFieldType.compatibleWithFormulaTypes('number'),
    ]
  }

  getComponent() {
    return GenericViewAggregation
  }

  formatValue(value, { field, fieldType }) {
    if (isNaN(value)) {
      return null
    }
    return fieldType.toHumanReadableString(field, value)
  }
}

export class DistributionViewAggregationType extends ViewAggregationType {
  static getType() {
    return 'distribution'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewAggregationType.distribution')
  }

  getShortName() {
    return 'Dist.'
  }

  getCompatibleFieldTypes() {
    return [
      'text',
      'long_text',
      'url',
      'number',
      'rating',
      'date',
      'last_modified',
      'last_modified_by',
      'created_on',
      'created_by',
      'email',
      'phone_number',
      'single_select',
      'duration',
      'boolean',
      FormulaFieldType.compatibleWithFormulaTypes(
        'text',
        'char',
        'date',
        'number',
        'boolean'
      ),
    ]
  }

  getComponent() {
    return DistributionAggregation
  }

  getValue(value, { rowCount }) {
    // Value is returned from the server as an array of arrays,
    // each inner array representing one value of the distribution
    // and its corresponding count of occurrences. This function
    // calculates the corresponding percentages for each value and
    // adds it to each inner array as formatted strings ready for
    // display. Example:
    // Input:
    //   value = [
    //     ["Blue", 3],
    //     ["Red", 6]
    //   ]
    //   rowCount = 10
    // Output:
    //   [
    //     ["Blue", "(3)", "30%"],
    //     ["Red", "(6)", "60%"],
    //     ["Others", "(1)", "10%"]
    //   ]
    if (!value) {
      return null
    }

    const results = value.map(([label, count]) => {
      const percentage = Math.round((count / rowCount) * 100)
      return [label, `(${Number(count).toLocaleString()})`, `${percentage}%`]
    })

    // If the total row count is higher than the sum of distribution counts,
    // we need to add an "Others" entry to account for them. This can happen
    // because the server only sends the top ten distributions by count. If
    // there were more than ten unique values, the rest need to be represented
    // as a single entry named "Others"
    const othersCount =
      rowCount - value.reduce((sum, current) => sum + current[1], 0)
    if (othersCount > 0) {
      const percentage = Math.round((othersCount / rowCount) * 100)
      results.push([
        undefined,
        `(${othersCount.toLocaleString()})`,
        `${percentage}%`,
      ])
    }

    return results
  }
}
