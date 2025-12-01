import moment from '@baserow/modules/core/moment'
import _ from 'lodash'
import { Registerable } from '@baserow/modules/core/registry'
import ViewFilterTypeText from '@baserow/modules/database/components/view/ViewFilterTypeText'
import ViewFilterTypeNumber from '@baserow/modules/database/components/view/ViewFilterTypeNumber'
import ViewFilterTypeDuration from '@baserow/modules/database/components/view/ViewFilterTypeDuration'
import ViewFilterTypeRating from '@baserow/modules/database/components/view/ViewFilterTypeRating'
import ViewFilterTypeSelectOptions from '@baserow/modules/database/components/view/ViewFilterTypeSelectOptions'
import ViewFilterTypeBoolean from '@baserow/modules/database/components/view/ViewFilterTypeBoolean'
import ViewFilterTypeDateUpgradeToMultiStep from '@baserow/modules/database/components/view/ViewFilterTypeDateUpgradeToMultiStep'
import ViewFilterTypeNumberWithTimeZone from '@baserow/modules/database/components/view/ViewFilterTypeNumberWithTimeZone'
import ViewFilterTypeMultiStepDate from '@baserow/modules/database/components/view/ViewFilterTypeMultiStepDate'
import ViewFilterTypeLinkRow from '@baserow/modules/database/components/view/ViewFilterTypeLinkRow'
import ViewFilterTypeMultipleSelectOptions from '@baserow/modules/database/components/view/ViewFilterTypeMultipleSelectOptions'
import { trueValues } from '@baserow/modules/core/utils/constants'
import {
  splitTimezoneAndFilterValue,
  prepareMultiStepDateValue,
  DATE_FILTER_VALUE_SEPARATOR,
  splitMultiStepDateValue,
  DATE_FILTER_OPERATOR_DELTA_MAP,
  DATE_FILTER_OPERATOR_BOUNDS,
  DateFilterOperators,
} from '@baserow/modules/database/utils/date'
import { isInteger } from '@baserow/modules/core/utils/string'
import ViewFilterTypeFileTypeDropdown from '@baserow/modules/database/components/view/ViewFilterTypeFileTypeDropdown'
import ViewFilterTypeCollaborators from '@baserow/modules/database/components/view/ViewFilterTypeCollaborators'
import {
  FormulaFieldType,
  NumberFieldType,
} from '@baserow/modules/database/fieldTypes'

export class ViewFilterType extends Registerable {
  /**
   * A human readable name of the view filter type.
   */
  getName() {
    return null
  }

  getExample() {
    return 'string'
  }

  constructor(...args) {
    super(...args)
    this.type = this.getType()
    this.example = this.getExample()
    this.compatibleFieldTypes = this.getCompatibleFieldTypes()

    if (this.type === null) {
      throw new Error('The type name of a view type must be set.')
    }
    if (this.name === null) {
      throw new Error('The name of a view type must be set.')
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
   * Should return a component that is responsible for the filter's value. For example
   * for the equal filter a text field will be added where the user can enter whatever
   * they want to filter on.
   */
  getInputComponent() {
    return null
  }

  /**
    Informs forms whether the component returned by getInputComponent
    is user configurable, or just displays static data which they can't alter.
   */
  get hasEditableValue() {
    return true
  }

  /**
   * Should return the default value when a new filter of this type is created. In
   * almost all cases this should be an empty string, but with timezone sensitive
   * filters we might want use the current timezone.
   */
  getDefaultValue(field) {
    return ''
  }

  /**
   * Optionally, right before updating the string value can be prepared. This could for
   * example be used to convert the value to a number.
   */
  prepareValue(value, field) {
    return String(value ?? '')
  }

  /**
   * Should return the field type names that the filter is compatible with or
   * functions which take a field and return a boolean indicating if the field is
   * compatible or not.
   *
   * So for example ['text', 'long_text']. When that field is selected as filter it
   * is only possible to select compatible filter types.
   *
   * Or using a function you could do [(field) => field.some_prop === 10, 'long_text']
   * and then fields which pass the test defined by the function will be deemed as
   * compatible.
   *
   * If no filters are compatible with a field then that field will be disabled.
   */
  getCompatibleFieldTypes() {
    return []
  }

  /**
   * Determines whether the particular filter type will be available
   * in public views.
   */
  isAllowedInPublicViews() {
    return true
  }

  /**
   * Returns if a given field is compatible with this view filter or not.
   *
   * Checks compatibility by resolving the field's canonical filter type via
   * getCompatibleFilterFieldType(field) and then matching against
   * this.compatibleFieldTypes (strings or predicates).
   */
  fieldIsCompatible(field) {
    // Resolve the canonical field type for filter compatibility.
    const fieldType = this.app.$registry.get('field', field.type)
    const canonicalFieldType = fieldType
      ? fieldType.getCompatibleFilterFieldType(field)
      : fieldType

    const compareType = canonicalFieldType
      ? canonicalFieldType.constructor.getType()
      : field.type

    // Check static compatible list and predicates
    for (const typeOrFunc of this.compatibleFieldTypes) {
      if (typeOrFunc instanceof Function) {
        if (typeOrFunc(field)) {
          return true
        }
      } else if (compareType === typeOrFunc) {
        return true
      }
    }

    return false
  }

  /**
   * Given a field and a map of field types to values, this method will return the
   * value that is compatible with the field. If no value is found the notFoundValue
   * will be returned.
   * This can be used to verify if a field is compatible with a filter type or to
   * return the correct component for the filter input.
   *
   * @param {object} field The field object that should be checked.
   * @param {object} valuesMap A list of tuple where the key is the field type or a function
   * that takes a field and returns a boolean and the value is the value that should be
   * returned if the field is compatible.
   * @param {any} notFoundValue The value that should be returned if no compatible value
   * is found.
   * @returns {any} The value that is compatible with the field or the notFoundValue.
   */
  getCompatibleFieldValue(field, valuesMap, notFoundValue = null) {
    // Resolve the canonical field type for filter compatibility.
    const fieldType = this.app?.$registry?.get('field', field.type)
    const canonicalFieldType = fieldType
      ? fieldType.getCompatibleFilterFieldType(field)
      : fieldType
    const compareType = canonicalFieldType
      ? canonicalFieldType.constructor.getType()
      : field.type

    for (const [typeOrFunc, value] of valuesMap) {
      if (typeOrFunc instanceof Function) {
        if (typeOrFunc(field)) {
          return value
        }
      } else if (compareType === typeOrFunc) {
        return value
      }
    }
    return notFoundValue
  }

  /**
   * In order to real time check if the row applies to the filters we also need to
   * check on the web-frontend side if the value matches. Should return true if the
   * rowValue applies to the filterValue. This is really unfortunate in my opinion
   * because basically have the same code twice, but I could not think of an
   * alternative solution where we keep the real time check and we don't have
   * to wait for the server in order to tell us if the value matches.
   */
  matches(rowValue, filterValue, field, fieldType) {
    throw new Error('The matches method must be implemented for every filter.')
  }

  /**
   * Mark a filter type as deprecated. Deprecated filter types will not be shown in the
   * filter type dropdown in the frontend, but will still be available for existing
   * filters.
   * @returns {boolean} Whether the filter type is deprecated or not.
   */
  isDeprecated() {
    return false
  }
}

/**
 * Base class for field-type specific filtering details.
 *
 * In some cases we want to have per field-type handling of certain aspects of
 * a filter: input component selection and value parsing logic.
 *
 * This is a base class defining common interface for such customizations
 */
class SpecificFieldViewFilterHandler {
  getInputComponent() {
    return null
  }

  parseRowValue(value, field, fieldType) {
    return value
  }

  parseFilterValue(value, field, fieldType) {
    return value
  }
}

/**
 * Handle duration-specific filtering aspects:
 *
 * * input component should understand duration formats
 * * values should be parsed to duration value (a number of seconds).
 *
 *
 * Parsing is especially important because duration parsing result depends on duration
 * format picked. Filter value is passed as a string, and in case of duration, backend
 * will send a number of seconds. This, however, may be parsed as a number of minutes
 * or hours if a duration format picked uses minutes or hours as a lowest unit (i.e.
 * `d h m` or `d h` format).
 *
 * In case of parsing, this class ensures that a number string is passed as a Number
 * type to be consistent with backend's behavior.
 *
 */
class DurationFieldViewFilterHandler extends SpecificFieldViewFilterHandler {
  getInputComponent() {
    return ViewFilterTypeDuration
  }

  _parseDuration(value, field, fieldType) {
    if (String(value === null ? '' : value).trim() === '') {
      return null
    }

    const parsedValue = Number(value)
    if (_.isFinite(parsedValue)) {
      value = parsedValue
    }
    return fieldType.parseInputValue(field, value)
  }

  parseRowValue(value, field, fieldType) {
    // already processed, can be returned as-is.
    if (_.isInteger(value)) {
      return value
    }
    return fieldType.parseInputValue(field, value)
  }

  parseFilterValue(value, field, fieldType) {
    return this._parseDuration(value, field, fieldType)
  }
}

class TextLikeFieldViewFilterHandler extends SpecificFieldViewFilterHandler {
  getInputComponent() {
    return ViewFilterTypeText
  }

  parseRowValue(value, field, fieldType) {
    return (value === null ? '' : value).toString().toLowerCase().trim()
  }

  parseFilterValue(value, field, fieldType) {
    return (value === null ? '' : value).toString().toLowerCase().trim()
  }
}

class RatingFieldViewFilterHandler extends SpecificFieldViewFilterHandler {
  getInputComponent() {
    return ViewFilterTypeRating
  }

  parseRowValue(value, field, fieldType) {
    if (value === '' || value === null) {
      return NaN
    }
    return Number(value.toString().toLowerCase().trim())
  }

  parseFilterValue(value, field, fieldType) {
    if (value === '' || value === null) {
      return NaN
    }
    return Number(value.toString().toLowerCase().trim())
  }
}

class NumberFieldViewFilterHandler extends SpecificFieldViewFilterHandler {
  getInputComponent() {
    return ViewFilterTypeNumber
  }

  _parseNumberValue(value) {
    if (value === '' || value === null) {
      return NaN
    }
    return Number(value.toString().toLowerCase().trim())
  }

  parseRowValue(value, field, fieldType) {
    return this._parseNumberValue(value)
  }

  parseFilterValue(value, field, fieldType) {
    return this._parseNumberValue(value)
  }
}

class SpecificFieldFilterType extends ViewFilterType {
  getFieldsMapping() {
    const map = [
      ['duration', new DurationFieldViewFilterHandler()],
      [
        FormulaFieldType.compatibleWithFormulaTypes('duration'),
        new DurationFieldViewFilterHandler(),
      ],
      ['rating', new RatingFieldViewFilterHandler()],
      ['number', new NumberFieldViewFilterHandler()],
      [
        FormulaFieldType.compatibleWithFormulaTypes('number'),
        new NumberFieldViewFilterHandler(),
      ],
      ['autonumber', new NumberFieldViewFilterHandler()],
    ]
    return map
  }

  getSpecificFieldFilterType(field) {
    const map = this.getFieldsMapping()
    return this.getCompatibleFieldValue(
      field,
      map,
      new TextLikeFieldViewFilterHandler()
    )
  }

  getMatchesParsedValues(rowValue, filterValue, field, fieldType) {
    const specificFieldType = this.getSpecificFieldFilterType(field)
    const parsedRowValue = specificFieldType.parseRowValue(
      rowValue,
      field,
      fieldType
    )
    const parsedFilterValue = specificFieldType.parseFilterValue(
      filterValue,
      field,
      fieldType
    )
    return { rowVal: parsedRowValue, filterVal: parsedFilterValue }
  }

  getInputComponent(field) {
    return this.getSpecificFieldFilterType(field).getInputComponent()
  }
}

export class EqualViewFilterType extends SpecificFieldFilterType {
  static getType() {
    return 'equal'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.is')
  }

  getCompatibleFieldTypes() {
    return [
      'text',
      'long_text',
      'url',
      'email',
      'number',
      'rating',
      'phone_number',
      'uuid',
      'autonumber',
      'duration',
      FormulaFieldType.compatibleWithFormulaTypes(
        'text',
        'char',
        'number',
        'duration',
        'url'
      ),
    ]
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (rowValue === null) {
      rowValue = ''
    }
    const { rowVal, filterVal } = this.getMatchesParsedValues(
      rowValue,
      filterValue,
      field,
      fieldType
    )

    if (filterVal === '') {
      return null
    }
    return rowVal === filterVal
  }
}

export class NotEqualViewFilterType extends SpecificFieldFilterType {
  static getType() {
    return 'not_equal'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isNot')
  }

  getCompatibleFieldTypes() {
    return [
      'text',
      'long_text',
      'url',
      'email',
      'number',
      'rating',
      'phone_number',
      'uuid',
      'autonumber',
      'duration',
      FormulaFieldType.compatibleWithFormulaTypes(
        'text',
        'char',
        'number',
        'duration',
        'url'
      ),
    ]
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (rowValue === null) {
      rowValue = ''
    }

    const { rowVal, filterVal } = this.getMatchesParsedValues(
      rowValue,
      filterValue,
      field,
      fieldType
    )

    if (filterVal === '') {
      return null
    }

    return rowVal !== filterVal
  }
}

export class FilenameContainsViewFilterType extends ViewFilterType {
  static getType() {
    return 'filename_contains'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.filenameContains')
  }

  getInputComponent() {
    return ViewFilterTypeText
  }

  getCompatibleFieldTypes() {
    return [
      'file',
      FormulaFieldType.compatibleWithFormulaTypes(
        FormulaFieldType.arrayOf('single_file')
      ),
    ]
  }

  matches(rowValue, filterValue, field, fieldType) {
    return fieldType.containsFilter(rowValue, filterValue, field)
  }
}

export class HasFileTypeViewFilterType extends ViewFilterType {
  static getType() {
    return 'has_file_type'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasFileType')
  }

  getExample() {
    return 'image | document'
  }

  getInputComponent() {
    return ViewFilterTypeFileTypeDropdown
  }

  getCompatibleFieldTypes() {
    return [
      'file',
      FormulaFieldType.compatibleWithFormulaTypes(
        FormulaFieldType.arrayOf('single_file')
      ),
    ]
  }

  matches(rowValue, filterValue, field, fieldType) {
    const isImage = filterValue === 'image'
    const isDocument = filterValue === 'document'

    if (!isImage && !isDocument) {
      return true
    }

    for (let i = 0; i < rowValue.length; i++) {
      if (rowValue[i].is_image === isImage) {
        return true
      }
    }

    return false
  }
}

export class FilesLowerThanViewFilterType extends ViewFilterType {
  static getType() {
    return 'files_lower_than'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.filesLowerThan')
  }

  getExample() {
    return '2'
  }

  getInputComponent() {
    return ViewFilterTypeNumber
  }

  getCompatibleFieldTypes() {
    return ['file']
  }

  matches(rowValue, filterValue, field, fieldType) {
    return rowValue.length < parseInt(filterValue)
  }
}

export class ContainsViewFilterType extends ViewFilterType {
  static getType() {
    return 'contains'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.contains')
  }

  getInputComponent(field) {
    const inputComponent = {
      [NumberFieldType.getType()]: ViewFilterTypeNumber,
    }
    return inputComponent[field?.type] || ViewFilterTypeText
  }

  getCompatibleFieldTypes() {
    return [
      'text',
      'long_text',
      'url',
      'email',
      'phone_number',
      'date',
      'last_modified',
      'created_on',
      'single_select',
      'multiple_select',
      'number',
      'autonumber',
      FormulaFieldType.compatibleWithFormulaTypes(
        'text',
        'char',
        'number',
        'date',
        'url',
        'single_select',
        'multiple_select'
      ),
    ]
  }

  matches(rowValue, filterValue, field, fieldType) {
    return fieldType.containsFilter(rowValue, filterValue, field)
  }
}

export class ContainsNotViewFilterType extends ViewFilterType {
  static getType() {
    return 'contains_not'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.containsNot')
  }

  getInputComponent(field) {
    const inputComponent = {
      [NumberFieldType.getType()]: ViewFilterTypeNumber,
    }
    return inputComponent[field?.type] || ViewFilterTypeText
  }

  getCompatibleFieldTypes() {
    return [
      'text',
      'long_text',
      'url',
      'email',
      'phone_number',
      'date',
      'last_modified',
      'created_on',
      'single_select',
      'multiple_select',
      'number',
      'autonumber',
      FormulaFieldType.compatibleWithFormulaTypes(
        'text',
        'char',
        'number',
        'date',
        'url',
        'single_select',
        'multiple_select'
      ),
    ]
  }

  matches(rowValue, filterValue, field, fieldType) {
    return fieldType.notContainsFilter(rowValue, filterValue, field)
  }
}

export class ContainsWordViewFilterType extends ViewFilterType {
  static getType() {
    return 'contains_word'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.containsWord')
  }

  getInputComponent(field) {
    return ViewFilterTypeText
  }

  getCompatibleFieldTypes() {
    return [
      'text',
      'long_text',
      'url',
      'email',
      'single_select',
      'multiple_select',
      FormulaFieldType.compatibleWithFormulaTypes(
        'text',
        'char',
        'url',
        'single_select',
        'multiple_select'
      ),
    ]
  }

  matches(rowValue, filterValue, field, fieldType) {
    return fieldType.containsWordFilter(rowValue, filterValue, field)
  }
}

export class DoesntContainWordViewFilterType extends ContainsWordViewFilterType {
  static getType() {
    return 'doesnt_contain_word'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.doesntContainWord')
  }

  matches(rowValue, filterValue, field, fieldType) {
    return fieldType.doesntContainWordFilter(rowValue, filterValue, field)
  }
}

export class LengthIsLowerThanViewFilterType extends ViewFilterType {
  static getType() {
    return 'length_is_lower_than'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.lengthIsLowerThan')
  }

  getExample() {
    return '5'
  }

  getInputComponent() {
    return ViewFilterTypeNumber
  }

  getCompatibleFieldTypes() {
    return [
      'text',
      'long_text',
      'url',
      'email',
      'phone_number',
      FormulaFieldType.compatibleWithFormulaTypes('url'),
    ]
  }

  matches(rowValue, filterValue, field, fieldType) {
    return (
      isNaN(filterValue) ||
      rowValue === null ||
      filterValue === 0 ||
      rowValue.toString().length < filterValue
    )
  }
}

export class BaseDateMultiStepViewFilterType extends ViewFilterType {
  getExample() {
    return 'UTC??today'
  }

  getInputComponent() {
    return ViewFilterTypeMultiStepDate
  }

  getDefaultTimezone(field) {
    return field.date_force_timezone || moment.tz.guess()
  }

  getFilterDate(operatorValue, filterValue, timezone) {
    const filterDate = moment.utc()
    if (timezone) {
      filterDate.tz(timezone)
    }
    if (DATE_FILTER_OPERATOR_DELTA_MAP[operatorValue] !== undefined) {
      return DATE_FILTER_OPERATOR_DELTA_MAP[operatorValue](
        filterDate,
        filterValue,
        timezone
      )
    } else {
      return filterDate
    }
  }

  getCompatibleOperators() {
    const incompatibleOprs = this.getIncompatibleOperators()
    return Object.values(DateFilterOperators).filter(
      (opr) => !incompatibleOprs.includes(opr.value)
    )
  }

  getIncompatibleOperators() {
    return []
  }

  prepareValue(value, field, filterChanged = false) {
    const sep = DATE_FILTER_VALUE_SEPARATOR
    const [, filterValue, operator] = splitMultiStepDateValue(value, sep)
    const timezone = this.getDefaultTimezone(field)
    return value && !filterChanged
      ? value
      : `${timezone}${sep}${filterValue}${sep}${operator}`
  }

  localizeRowValue(rowValue, timezone) {
    const localizedRowValue = moment.utc(rowValue)
    if (timezone !== null) {
      localizedRowValue.tz(timezone)
    }
    return localizedRowValue
  }

  rowMatches(rowDate, lowerBound, upperBound) {
    throw new Error(
      'The rowMatches method must be implemented for every filter.'
    )
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (rowValue === null) {
      return false
    }

    const sep = DATE_FILTER_VALUE_SEPARATOR
    const [timezone, value, operatorValue] = splitMultiStepDateValue(
      filterValue,
      sep
    )

    // Check if the operator is compatible with the filter type.
    const operator = this.getCompatibleOperators().find(
      (opr) => opr.value === operatorValue
    )
    if (!operator) {
      return false
    } else if (operator.hasNrInputValue && value === '') {
      return true // return all the rows if a proper value has not been set yet.
    }

    let filterDate
    try {
      filterDate = this.getFilterDate(operatorValue, value, timezone)
    } catch {
      return false
    }

    // Localize the filter date and the row date.
    const rowDate = this.localizeRowValue(rowValue, timezone)
    const [lowerBound, upperBound] =
      DATE_FILTER_OPERATOR_BOUNDS[operatorValue](filterDate)

    return this.rowMatches(rowDate, lowerBound, upperBound, timezone)
  }
}

export class DateMultiStepViewFilterType extends BaseDateMultiStepViewFilterType {
  getCompatibleFieldTypes() {
    return [
      'date',
      'last_modified',
      'created_on',
      FormulaFieldType.compatibleWithFormulaTypes('date'),
    ]
  }
}

export class DateIsEqualMultiStepViewFilterType extends DateMultiStepViewFilterType {
  static getType() {
    return 'date_is'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.is')
  }

  rowMatches(rowDate, lowerBound, upperBound, timezone) {
    return rowDate.isSameOrAfter(lowerBound) && rowDate.isBefore(upperBound)
  }
}

export class DateIsNotEqualMultiStepViewFilterType extends DateIsEqualMultiStepViewFilterType {
  static getType() {
    return 'date_is_not'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isNot')
  }

  rowMatches(rowDate, lowerBound, upperBound, timezone) {
    return !super.rowMatches(rowDate, lowerBound, upperBound, timezone)
  }
}

export class DateIsBeforeMultiStepViewFilterType extends DateMultiStepViewFilterType {
  static getType() {
    return 'date_is_before'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isBefore')
  }

  rowMatches(rowDate, lowerBound, upperBound, timezone) {
    return rowDate.isBefore(lowerBound)
  }
}

export class DateIsOnOrBeforeMultiStepViewFilterType extends DateMultiStepViewFilterType {
  static getType() {
    return 'date_is_on_or_before'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isOnOrBefore')
  }

  rowMatches(rowDate, lowerBound, upperBound, timezone) {
    return rowDate.isBefore(upperBound)
  }
}

export class DateIsAfterMultiStepViewFilterType extends DateMultiStepViewFilterType {
  static getType() {
    return 'date_is_after'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isAfter')
  }

  rowMatches(rowDate, lowerBound, upperBound, timezone) {
    return rowDate.isSameOrAfter(upperBound, 'second')
  }
}

export class DateIsOnOrAfterMultiStepViewFilterType extends DateMultiStepViewFilterType {
  static getType() {
    return 'date_is_on_or_after'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isOnOrAfter')
  }

  rowMatches(rowDate, lowerBound, upperBound, timezone) {
    return rowDate.isSameOrAfter(lowerBound)
  }
}

export class DateIsWithinMultiStepViewFilterType extends DateMultiStepViewFilterType {
  static getType() {
    return 'date_is_within'
  }

  getIncompatibleOperators() {
    return [DateFilterOperators.TODAY.value]
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isWithin')
  }

  rowMatches(rowDate, lowerBound, upperBound, timezone) {
    const startOfToday = moment.utc()
    if (timezone) {
      startOfToday.tz(timezone)
    }
    startOfToday.startOf('day')

    let start = lowerBound
    let end = upperBound
    if (startOfToday.isBefore(upperBound)) {
      start = startOfToday
    } else {
      end = startOfToday.add(1, 'day')
    }
    return rowDate.isSameOrAfter(start) && rowDate.isBefore(end)
  }
}

// DEPRECATED: This filter type is deprecated and should not be used anymore. It will
// be removed in the future. Please use the DateMultiStepViewFilterType instead.
class LocalizedDateViewFilterType extends ViewFilterType {
  isDeprecated() {
    return true
  }

  getSeparator() {
    return DATE_FILTER_VALUE_SEPARATOR
  }

  getDateFormat() {
    return 'YYYY-MM-DD'
  }

  getDefaultTimezone(field) {
    return field.date_force_timezone || moment.tz.guess()
  }

  splitTimezoneAndValue(value) {
    return splitTimezoneAndFilterValue(value, this.getSeparator())
  }

  getInputComponent() {
    return ViewFilterTypeDateUpgradeToMultiStep
  }

  prepareValue(value, field, filterChanged = false) {
    const [, filterValue] = this.splitTimezoneAndValue(value)
    const timezone = this.getDefaultTimezone(field)
    return value && !filterChanged ? value : `${timezone}?${filterValue}`
  }
}

export class DateEqualViewFilterType extends LocalizedDateViewFilterType {
  static getType() {
    return 'date_equal'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isDate')
  }

  getExample() {
    return '2020-01-01'
  }

  migrateToNewMultiStepDateFilter(filterValue) {
    const [timezone, value] = this.splitTimezoneAndValue(filterValue)
    return {
      type: DateIsEqualMultiStepViewFilterType.getType(),
      value: prepareMultiStepDateValue(
        value,
        timezone,
        DateFilterOperators.EXACT_DATE.value
      ),
    }
  }

  getCompatibleFieldTypes() {
    return [
      'date',
      'last_modified',
      'created_on',
      FormulaFieldType.compatibleWithFormulaTypes('date'),
    ]
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (rowValue === null) {
      return false
    }

    const [timezone, dateValue] = this.splitTimezoneAndValue(filterValue)
    const filterDate = moment.utc(dateValue, this.getDateFormat(), true)
    const rowDate = moment.utc(rowValue)
    if (timezone !== null) {
      filterDate.tz(timezone, true)
      rowDate.tz(timezone)
    }

    return dateValue === '' || rowDate.isSame(filterDate, 'date')
  }
}

// DEPRECATED
export class DateNotEqualViewFilterType extends LocalizedDateViewFilterType {
  static getType() {
    return 'date_not_equal'
  }

  migrateToNewMultiStepDateFilter(filterValue) {
    const [timezone, value] = this.splitTimezoneAndValue(filterValue)
    return {
      type: DateIsNotEqualMultiStepViewFilterType.getType(),
      value: prepareMultiStepDateValue(
        value,
        timezone,
        DateFilterOperators.EXACT_DATE.value
      ),
    }
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isNotDate')
  }

  getExample() {
    return '2020-01-01'
  }

  getCompatibleFieldTypes() {
    return [
      'date',
      'last_modified',
      'created_on',
      FormulaFieldType.compatibleWithFormulaTypes('date'),
    ]
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (rowValue === null) {
      return true
    }

    const [timezone, dateValue] = this.splitTimezoneAndValue(filterValue)
    const filterDate = moment.utc(dateValue, this.getDateFormat(), true)
    const rowDate = moment.utc(rowValue)

    if (timezone !== null) {
      filterDate.tz(timezone, true)
      rowDate.tz(timezone)
    }

    return dateValue === '' || !rowDate.isSame(filterDate, 'date')
  }
}

// DEPRECATED
export class DateBeforeViewFilterType extends LocalizedDateViewFilterType {
  static getType() {
    return 'date_before'
  }

  migrateToNewMultiStepDateFilter(filterValue) {
    const [timezone, value] = this.splitTimezoneAndValue(filterValue)
    return {
      type: DateIsBeforeMultiStepViewFilterType.getType(),
      value: prepareMultiStepDateValue(
        value,
        timezone,
        DateFilterOperators.EXACT_DATE.value
      ),
    }
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isBeforeDate')
  }

  getExample() {
    return '2020-01-01'
  }

  getCompatibleFieldTypes() {
    return [
      'date',
      'last_modified',
      'created_on',
      FormulaFieldType.compatibleWithFormulaTypes('date'),
    ]
  }

  matches(rowValue, filterValue, field, fieldType) {
    const [timezone, dateValue] = this.splitTimezoneAndValue(filterValue)
    const filterDate = moment.utc(dateValue, this.getDateFormat(), true)
    const rowDate = moment.utc(rowValue)

    // without a valid date the filter won't be applied
    if (!filterDate.isValid()) {
      return true
    }

    // an invalid date will be filtered out
    if (rowValue === null || !rowDate.isValid()) {
      return false
    }

    if (timezone !== null) {
      filterDate.tz(timezone, true)
      rowDate.tz(timezone)
    }

    return rowDate.isBefore(filterDate, 'day')
  }
}

// DEPRECATED
export class DateBeforeOrEqualViewFilterType extends LocalizedDateViewFilterType {
  static getType() {
    return 'date_before_or_equal'
  }

  migrateToNewMultiStepDateFilter(filterValue) {
    const [timezone, value] = this.splitTimezoneAndValue(filterValue)
    return {
      type: DateIsOnOrBeforeMultiStepViewFilterType.getType(),
      value: prepareMultiStepDateValue(
        value,
        timezone,
        DateFilterOperators.EXACT_DATE.value
      ),
    }
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isBeforeOrEqualDate')
  }

  getExample() {
    return '2020-01-01'
  }

  getCompatibleFieldTypes() {
    return [
      'date',
      'last_modified',
      'created_on',
      FormulaFieldType.compatibleWithFormulaTypes('date'),
    ]
  }

  matches(rowValue, filterValue, field, fieldType) {
    const [timezone, dateValue] = this.splitTimezoneAndValue(filterValue)
    const filterDate = moment.utc(dateValue, this.getDateFormat(), true)
    const rowDate = moment.utc(rowValue)

    // without a valid date the filter won't be applied
    if (!filterDate.isValid()) {
      return true
    }

    // an invalid date will be filtered out
    if (rowValue === null || !rowDate.isValid()) {
      return false
    }

    if (timezone !== null) {
      filterDate.tz(timezone, true)
      rowDate.tz(timezone)
    }

    return rowDate.isSameOrBefore(filterDate, 'day')
  }
}

// DEPRECATED
export class DateAfterViewFilterType extends LocalizedDateViewFilterType {
  static getType() {
    return 'date_after'
  }

  migrateToNewMultiStepDateFilter(filterValue) {
    const [timezone, value] = this.splitTimezoneAndValue(filterValue)
    return {
      type: DateIsAfterMultiStepViewFilterType.getType(),
      value: prepareMultiStepDateValue(
        value,
        timezone,
        DateFilterOperators.EXACT_DATE.value
      ),
    }
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isAfterDate')
  }

  getExample() {
    return '2020-01-01'
  }

  getCompatibleFieldTypes() {
    return [
      'date',
      'last_modified',
      'created_on',
      FormulaFieldType.compatibleWithFormulaTypes('date'),
    ]
  }

  matches(rowValue, filterValue, field, fieldType) {
    const [timezone, dateValue] = this.splitTimezoneAndValue(filterValue)
    const filterDate = moment.utc(dateValue, this.getDateFormat(), true)
    const rowDate = moment.utc(rowValue)
    if (timezone !== null) {
      filterDate.tz(timezone, true)
      rowDate.tz(timezone)
    }

    // without a valid date the filter won't be applied
    if (!filterDate.isValid()) {
      return true
    }

    // an invalid date will be filtered out
    if (rowValue === null || !rowDate.isValid()) {
      return false
    }
    return rowDate.isAfter(filterDate, 'day')
  }
}

// DEPRECATED
export class DateAfterDaysAgoViewFilterType extends LocalizedDateViewFilterType {
  static getType() {
    return 'date_after_days_ago'
  }

  migrateToNewMultiStepDateFilter(filterValue) {
    const [timezone, value] = this.splitTimezoneAndValue(filterValue)
    return {
      type: DateIsOnOrAfterMultiStepViewFilterType.getType(),
      value: prepareMultiStepDateValue(
        value,
        timezone,
        DateFilterOperators.NR_DAYS_AGO.value
      ),
    }
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isAfterDaysAgo')
  }

  getExample() {
    return '20'
  }

  getCompatibleFieldTypes() {
    return [
      'date',
      'last_modified',
      'created_on',
      FormulaFieldType.compatibleWithFormulaTypes('date'),
    ]
  }

  matches(rowValue, filterValue) {
    if (rowValue === null || !moment.utc(rowValue).isValid()) {
      return false
    }

    const [timezone, rawDaysAgo] = this.splitTimezoneAndValue(filterValue)
    const daysAgo = parseInt(rawDaysAgo, 10)

    if (isNaN(daysAgo)) {
      return false
    }

    // Convert rowValue to a date object and adjust to timezone if provided.
    let rowDate = moment.utc(rowValue)
    if (timezone !== null) {
      rowDate = rowDate.tz(timezone)
    }

    // Create a date object for current date and adjust to timezone if provided.
    let now = moment.utc()
    if (timezone !== null) {
      now = now.tz(timezone)
    }

    // Calculate the date daysAgo days from now.
    const daysAgoDate = now.subtract(daysAgo, 'days')

    // Check if rowDate is the same as or after daysAgoDate.
    return rowDate.isSameOrAfter(daysAgoDate, 'day')
  }
}

// DEPRECATED
export class DateAfterOrEqualViewFilterType extends LocalizedDateViewFilterType {
  static getType() {
    return 'date_after_or_equal'
  }

  migrateToNewMultiStepDateFilter(filterValue) {
    const [timezone, value] = this.splitTimezoneAndValue(filterValue)
    return {
      type: DateIsOnOrAfterMultiStepViewFilterType.getType(),
      value: prepareMultiStepDateValue(
        value,
        timezone,
        DateFilterOperators.EXACT_DATE.value
      ),
    }
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isAfterOrEqualDate')
  }

  getExample() {
    return '2020-01-01'
  }

  getCompatibleFieldTypes() {
    return [
      'date',
      'last_modified',
      'created_on',
      FormulaFieldType.compatibleWithFormulaTypes('date'),
    ]
  }

  matches(rowValue, filterValue, field, fieldType) {
    const [timezone, dateValue] = this.splitTimezoneAndValue(filterValue)
    const filterDate = moment.utc(dateValue, this.getDateFormat(), true)
    const rowDate = moment.utc(rowValue)
    if (timezone !== null) {
      filterDate.tz(timezone, true)
      rowDate.tz(timezone)
    }

    // without a valid date the filter won't be applied
    if (!filterDate.isValid()) {
      return true
    }

    // an invalid date will be filtered out
    if (rowValue === null || !rowDate.isValid()) {
      return false
    }
    return rowDate.isSameOrAfter(filterDate, 'day')
  }
}

// DEPRECATED
export class DateCompareTodayViewFilterType extends LocalizedDateViewFilterType {
  static getType() {
    throw new Error('Not implemented')
  }

  getName() {
    throw new Error('Not implemented')
  }

  isDateMatching(rowValue, today) {
    throw new Error('Not implemented')
  }

  getInputComponent() {
    return ViewFilterTypeDateUpgradeToMultiStep
  }

  getCompatibleFieldTypes() {
    return [
      'date',
      'last_modified',
      'created_on',
      FormulaFieldType.compatibleWithFormulaTypes('date'),
    ]
  }

  getDefaultValue(field) {
    return this.getDefaultTimezone(field)
  }

  prepareValue(value, field, filterChanged = false) {
    return value && !filterChanged ? value : `${this.getDefaultValue(field)}?`
  }

  getExample() {
    return 'UTC'
  }

  matches(rowValue, filterValue, field) {
    if (rowValue === null || !moment.utc(rowValue).isValid()) {
      return false
    }

    const [timezone] = this.splitTimezoneAndValue(filterValue)

    const rowDate = moment.utc(rowValue)
    const today = moment.utc()
    if (timezone !== null) {
      today.tz(timezone)
      rowDate.tz(timezone)
    }
    return this.isDateMatching(rowDate, today)
  }
}

// DEPRECATED
export class DateEqualsTodayViewFilterType extends DateCompareTodayViewFilterType {
  static getType() {
    return 'date_equals_today'
  }

  migrateToNewMultiStepDateFilter(filterValue) {
    const [timezone, dateValue] = this.splitTimezoneAndValue(filterValue)
    return {
      type: DateIsEqualMultiStepViewFilterType.getType(),
      value: prepareMultiStepDateValue(
        dateValue,
        timezone,
        DateFilterOperators.TODAY.value
      ),
    }
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isToday')
  }

  get hasEditableValue() {
    return false
  }

  isDateMatching(rowValue, today) {
    const minTime = today.clone().startOf('day')
    const maxtime = today.clone().endOf('day')
    return rowValue.isBetween(minTime, maxtime, null, '[]')
  }
}

// DEPRECATED
export class DateBeforeTodayViewFilterType extends DateCompareTodayViewFilterType {
  static getType() {
    return 'date_before_today'
  }

  migrateToNewMultiStepDateFilter(filterValue) {
    const [timezone, value] = this.splitTimezoneAndValue(filterValue)
    return {
      type: DateIsBeforeMultiStepViewFilterType.getType(),
      value: prepareMultiStepDateValue(
        value,
        timezone,
        DateFilterOperators.TODAY.value
      ),
    }
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.beforeToday')
  }

  get hasEditableValue() {
    return false
  }

  isDateMatching(rowValue, today) {
    const minTime = today.clone().startOf('day')
    return rowValue.isBefore(minTime)
  }
}

// DEPRECATED
export class DateAfterTodayViewFilterType extends DateCompareTodayViewFilterType {
  static getType() {
    return 'date_after_today'
  }

  migrateToNewMultiStepDateFilter(filterValue) {
    const [timezone, dateValue] = this.splitTimezoneAndValue(filterValue)
    return {
      type: DateIsAfterMultiStepViewFilterType.getType(),
      value: prepareMultiStepDateValue(
        dateValue,
        timezone,
        DateFilterOperators.TODAY.value
      ),
    }
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.afterToday')
  }

  get hasEditableValue() {
    return false
  }

  isDateMatching(rowValue, today) {
    const maxtime = today.clone().endOf('day')
    return rowValue.isAfter(maxtime)
  }
}

// DEPRECATED
export class DateEqualsCurrentWeekViewFilterType extends DateCompareTodayViewFilterType {
  static getType() {
    return 'date_equals_week'
  }

  migrateToNewMultiStepDateFilter(filterValue) {
    const [timezone, dateValue] = this.splitTimezoneAndValue(filterValue)
    return {
      type: DateIsEqualMultiStepViewFilterType.getType(),
      value: prepareMultiStepDateValue(
        dateValue,
        timezone,
        DateFilterOperators.THIS_WEEK.value
      ),
    }
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.inThisWeek')
  }

  isDateMatching(rowValue, today) {
    const firstDay = today.clone().startOf('isoWeek')
    const lastDay = today.clone().endOf('isoWeek')
    return rowValue.isBetween(firstDay, lastDay, null, '[]')
  }
}

// DEPRECATED
export class DateEqualsCurrentMonthViewFilterType extends DateCompareTodayViewFilterType {
  static getType() {
    return 'date_equals_month'
  }

  migrateToNewMultiStepDateFilter(filterValue) {
    const [timezone, dateValue] = this.splitTimezoneAndValue(filterValue)
    return {
      type: DateIsEqualMultiStepViewFilterType.getType(),
      value: prepareMultiStepDateValue(
        dateValue,
        timezone,
        DateFilterOperators.THIS_MONTH.value
      ),
    }
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.inThisMonth')
  }

  isDateMatching(rowValue, today) {
    const firstDay = today.clone().startOf('month')
    const lastDay = today.clone().endOf('month')
    return rowValue.isBetween(firstDay, lastDay, null, '[]')
  }
}

// DEPRECATED
export class DateEqualsCurrentYearViewFilterType extends DateEqualsTodayViewFilterType {
  static getType() {
    return 'date_equals_year'
  }

  migrateToNewMultiStepDateFilter(filterValue) {
    const [timezone, value] = this.splitTimezoneAndValue(filterValue)
    return {
      type: DateIsEqualMultiStepViewFilterType.getType(),
      value: prepareMultiStepDateValue(
        value,
        timezone,
        DateFilterOperators.THIS_YEAR.value
      ),
    }
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.inThisYear')
  }

  isDateMatching(rowValue, today) {
    const firstDay = today.clone().startOf('year')
    const lastDay = today.clone().endOf('year')
    return rowValue.isBetween(firstDay, lastDay, null, '[]')
  }
}

// DEPRECATED
export class LocalizedDateCompareViewFilterType extends LocalizedDateViewFilterType {
  getCompatibleFieldTypes() {
    return [
      'date',
      'last_modified',
      'created_on',
      FormulaFieldType.compatibleWithFormulaTypes('date'),
    ]
  }

  getExample() {
    const tzone = moment.tz.guess()
    const xAgo = 1
    return `${tzone}${this.getSeparator()}${xAgo}`
  }

  splitTimezoneAndXToCompare(field, rawValue) {
    const [timezone, value] = this.splitTimezoneAndValue(rawValue)

    let filterValue = value
    if (filterValue !== null) {
      filterValue = parseInt(filterValue)
    }

    filterValue = isNaN(filterValue) ? '' : filterValue
    return [timezone, filterValue]
  }

  getValidNumberWithTimezone(rawValue, field) {
    const [timezone, filterValue] = this.splitTimezoneAndXToCompare(
      field,
      rawValue
    )
    return `${timezone}${this.getSeparator()}${filterValue}`
  }

  getDefaultValue(field) {
    return this.getValidNumberWithTimezone(null, field)
  }

  prepareValue(value, field) {
    return this.getValidNumberWithTimezone(value, field)
  }

  getDateToCompare(xToCompare) {
    throw new Error('Not implemented')
  }

  isDateMatching(rowValue, dateToCompare, today) {
    throw new Error('Not implemented')
  }

  matches(rowValue, filterValue, field) {
    if (rowValue === null) {
      rowValue = ''
    }

    const [timezone, xToCompare] = this.splitTimezoneAndXToCompare(
      field,
      filterValue
    )

    // an invalid daysAgo will result in an empty filter
    if (xToCompare === '') {
      return true
    }

    let dateToCompare
    try {
      dateToCompare = this.getDateToCompare(xToCompare)
    } catch (e) {
      return false
    }

    const rowDate = moment.utc(rowValue)
    const today = moment.utc()
    if (timezone) {
      dateToCompare.tz(timezone)
      rowDate.tz(timezone)
      today.tz(timezone)
    }
    return this.isDateMatching(rowDate, dateToCompare, today)
  }
}

function isRowValueBetweenDays(rowValue, dateToCompare, today) {
  const [firstDay, lastDay] = dateToCompare.isSameOrBefore(today)
    ? [dateToCompare, today]
    : [today, dateToCompare]
  return rowValue.isBetween(firstDay, lastDay, 'days', '[]')
}

// DEPRECATED
export class DateWithinDaysViewFilterType extends LocalizedDateCompareViewFilterType {
  static getType() {
    return 'date_within_days'
  }

  migrateToNewMultiStepDateFilter(filterValue) {
    const [timezone, value] = this.splitTimezoneAndValue(filterValue)
    return {
      type: DateIsWithinMultiStepViewFilterType.getType(),
      value: prepareMultiStepDateValue(
        value,
        timezone,
        DateFilterOperators.NR_DAYS_FROM_NOW.value
      ),
    }
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isWithinDays')
  }

  getDateToCompare(xToCompare) {
    return moment.utc().add(parseInt(xToCompare), 'days')
  }

  isDateMatching(rowValue, dateToCompare, today) {
    return isRowValueBetweenDays(rowValue, dateToCompare, today)
  }
}

// DEPRECATED
export class DateWithinWeeksViewFilterType extends LocalizedDateCompareViewFilterType {
  static getType() {
    return 'date_within_weeks'
  }

  migrateToNewMultiStepDateFilter(filterValue) {
    const [timezone, value] = this.splitTimezoneAndValue(filterValue)
    return {
      type: DateIsWithinMultiStepViewFilterType.getType(),
      value: prepareMultiStepDateValue(
        value,
        timezone,
        DateFilterOperators.NR_WEEKS_FROM_NOW.value
      ),
    }
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isWithinWeeks')
  }

  getDateToCompare(xToCompare) {
    const numberOfWeeks = parseInt(xToCompare)
    if (numberOfWeeks === 0) {
      throw new Error('Number of weeks cannot be 0')
    }
    return moment.utc().add(numberOfWeeks, 'weeks')
  }

  isDateMatching(rowValue, dateToCompare, today) {
    return isRowValueBetweenDays(rowValue, dateToCompare, today)
  }
}

// DEPRECATED
export class DateWithinMonthsViewFilterType extends LocalizedDateCompareViewFilterType {
  static getType() {
    return 'date_within_months'
  }

  migrateToNewMultiStepDateFilter(filterValue) {
    const [timezone, value] = this.splitTimezoneAndValue(filterValue)
    return {
      type: DateIsWithinMultiStepViewFilterType.getType(),
      value: prepareMultiStepDateValue(
        value,
        timezone,
        DateFilterOperators.NR_MONTHS_FROM_NOW.value
      ),
    }
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isWithinMonths')
  }

  getDateToCompare(xToCompare) {
    const numberOfMonths = parseInt(xToCompare)
    if (numberOfMonths === 0) {
      throw new Error('Number of months cannot be 0')
    }
    return moment.utc().add(numberOfMonths, 'month')
  }

  isDateMatching(rowValue, dateToCompare, today) {
    return isRowValueBetweenDays(rowValue, dateToCompare, today)
  }
}

// DEPRECATED
export class DateEqualsDaysAgoViewFilterType extends LocalizedDateCompareViewFilterType {
  static getType() {
    return 'date_equals_days_ago'
  }

  migrateToNewMultiStepDateFilter(filterValue) {
    const [timezone, daysAgo] = this.splitTimezoneAndValue(filterValue)
    return {
      type: DateIsEqualMultiStepViewFilterType.getType(),
      value: prepareMultiStepDateValue(
        daysAgo,
        timezone,
        DateFilterOperators.NR_DAYS_AGO.value
      ),
    }
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isDaysAgo')
  }

  getDateToCompare(xToCompare) {
    return moment.utc().subtract(parseInt(xToCompare), 'days')
  }

  isDateMatching(rowValue, dateToCompare, today) {
    return rowValue.isSame(dateToCompare, 'day')
  }
}

// DEPRECATED
export class DateEqualsMonthsAgoViewFilterType extends LocalizedDateCompareViewFilterType {
  static getType() {
    return 'date_equals_months_ago'
  }

  migrateToNewMultiStepDateFilter(filterValue) {
    const [timezone, value] = this.splitTimezoneAndValue(filterValue)
    return {
      type: DateIsEqualMultiStepViewFilterType.getType(),
      value: prepareMultiStepDateValue(
        value,
        timezone,
        DateFilterOperators.NR_MONTHS_AGO.value
      ),
    }
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isMonthsAgo')
  }

  getDateToCompare(xToCompare) {
    return moment.utc().subtract(parseInt(xToCompare), 'months')
  }

  isDateMatching(rowValue, dateToCompare, today) {
    return rowValue.isSame(dateToCompare, 'month')
  }
}

// DEPRECATED
export class DateEqualsYearsAgoViewFilterType extends LocalizedDateCompareViewFilterType {
  static getType() {
    return 'date_equals_years_ago'
  }

  migrateToNewMultiStepDateFilter(filterValue) {
    const [timezone, value] = this.splitTimezoneAndValue(filterValue)
    return {
      type: DateIsEqualMultiStepViewFilterType.getType(),
      value: prepareMultiStepDateValue(
        value,
        timezone,
        DateFilterOperators.NR_YEARS_AGO.value
      ),
    }
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isYearsAgo')
  }

  getDateToCompare(xToCompare) {
    return moment.utc().subtract(parseInt(xToCompare), 'years')
  }

  isDateMatching(rowValue, dateToCompare, today) {
    return rowValue.isSame(dateToCompare, 'year')
  }
}

export class DateEqualsDayOfMonthViewFilterType extends LocalizedDateViewFilterType {
  isDeprecated() {
    return false
  }

  static getType() {
    return 'date_equals_day_of_month'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isDayOfMonth')
  }

  getExample() {
    return '1'
  }

  getInputComponent() {
    return ViewFilterTypeNumberWithTimeZone
  }

  isDateMatching(rowValue, dayOfMonth) {
    return rowValue.date() === dayOfMonth
  }

  getCompatibleFieldTypes() {
    return ['date', 'last_modified', 'created_on']
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (rowValue === null) {
      rowValue = ''
    }

    const [timezone, rawDayOfMonth] = this.splitTimezoneAndValue(filterValue)
    if (rawDayOfMonth === '') {
      return true
    }

    // an invalid daysAgo will result in an empty filter
    const dayOfMonth = parseInt(rawDayOfMonth)
    if (isNaN(dayOfMonth) || dayOfMonth < 1 || dayOfMonth > 31) {
      return false
    }

    let rowDate = moment.utc(rowValue)
    if (timezone !== null) {
      rowDate = rowDate.tz(timezone)
    }
    return this.isDateMatching(rowDate, dayOfMonth)
  }
}

// Base filter type for basic numeric comparisons. It defines common logic for
// 'lower than', 'lower than or equal', 'higher than' and 'higher than or equal'
// view filter types.
export class NumericComparisonViewFilterType extends SpecificFieldFilterType {
  getExample() {
    return '100'
  }

  getCompatibleFieldTypes() {
    return [
      'number',
      'rating',
      'autonumber',
      'duration',
      FormulaFieldType.compatibleWithFormulaTypes('number', 'duration'),
    ]
  }

  // This method should be implemented by subclasses to define their comparison logic.
  matches(rowValue, filterValue, field, fieldType) {
    throw new Error('matches method must be implemented by subclasses')
  }
}

export class HigherThanViewFilterType extends NumericComparisonViewFilterType {
  static getType() {
    return 'higher_than'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.higherThan')
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (filterValue === '') {
      return null
    }

    const { rowVal, filterVal } = this.getMatchesParsedValues(
      rowValue,
      filterValue,
      field,
      fieldType
    )
    return (
      Number.isFinite(rowVal) &&
      Number.isFinite(filterVal) &&
      rowVal > filterVal
    )
  }
}

export class HigherThanOrEqualViewFilterType extends NumericComparisonViewFilterType {
  static getType() {
    return 'higher_than_or_equal'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.higherThanOrEqual')
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (filterValue === '') {
      return null
    }

    const { rowVal, filterVal } = this.getMatchesParsedValues(
      rowValue,
      filterValue,
      field,
      fieldType
    )
    return (
      Number.isFinite(rowVal) &&
      Number.isFinite(filterVal) &&
      rowVal >= filterVal
    )
  }
}

export class LowerThanViewFilterType extends NumericComparisonViewFilterType {
  static getType() {
    return 'lower_than'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.lowerThan')
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (filterValue === '') {
      return null
    }
    const { rowVal, filterVal } = this.getMatchesParsedValues(
      rowValue,
      filterValue,
      field,
      fieldType
    )

    return (
      Number.isFinite(rowVal) &&
      Number.isFinite(filterVal) &&
      rowVal < filterVal
    )
  }
}

export class LowerThanOrEqualViewFilterType extends NumericComparisonViewFilterType {
  static getType() {
    return 'lower_than_or_equal'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.lowerThanOrEqual')
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (filterValue === '') {
      return null
    }

    const { rowVal, filterVal } = this.getMatchesParsedValues(
      rowValue,
      filterValue,
      field,
      fieldType
    )

    return (
      Number.isFinite(rowVal) &&
      Number.isFinite(filterVal) &&
      rowVal <= filterVal
    )
  }
}

export class IsEvenAndWholeViewFilterType extends ViewFilterType {
  static getType() {
    return 'is_even_and_whole'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isEvenAndWhole')
  }

  getExample() {
    return 'true'
  }

  get hasEditableValue() {
    return false
  }

  getCompatibleFieldTypes() {
    return [
      'number',
      'autonumber',
      FormulaFieldType.compatibleWithFormulaTypes('number'),
    ]
  }

  matches(rowValue, filterValue, field, fieldType) {
    rowValue = parseFloat(rowValue)
    return rowValue % 2 === 0 && Number.isInteger(rowValue)
  }
}

export class SingleSelectEqualViewFilterType extends ViewFilterType {
  static getType() {
    return 'single_select_equal'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.is')
  }

  getExample() {
    return '1'
  }

  getInputComponent() {
    return ViewFilterTypeSelectOptions
  }

  getCompatibleFieldTypes() {
    return [
      'single_select',
      FormulaFieldType.compatibleWithFormulaTypes('single_select'),
    ]
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (filterValue === '') {
      return null
    }

    return rowValue !== null && rowValue.id === parseInt(filterValue)
  }
}

export class SingleSelectNotEqualViewFilterType extends ViewFilterType {
  static getType() {
    return 'single_select_not_equal'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isNot')
  }

  getExample() {
    return '1'
  }

  getInputComponent() {
    return ViewFilterTypeSelectOptions
  }

  getCompatibleFieldTypes() {
    return [
      'single_select',
      FormulaFieldType.compatibleWithFormulaTypes('single_select'),
    ]
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (filterValue === '') {
      return null
    }

    return (
      rowValue === null ||
      (rowValue !== null && rowValue.id !== parseInt(filterValue))
    )
  }
}

export class SingleSelectIsAnyOfViewFilterType extends ViewFilterType {
  static getType() {
    return 'single_select_is_any_of'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isAnyOf')
  }

  getExample() {
    return '1,2'
  }

  getInputComponent() {
    return ViewFilterTypeMultipleSelectOptions
  }

  getCompatibleFieldTypes() {
    return [
      'single_select',
      FormulaFieldType.compatibleWithFormulaTypes('single_select'),
    ]
  }

  prepareValue(value, field) {
    const t = (this._prepareValue(value, field) || []).join(',')
    return t
  }

  /**
   * internal method to get an uniq array of ids for the filter or null, if there is no filter value
   *
   * @param value
   * @param field
   * @returns {any[]|*[]|null}
   * @private
   */
  _prepareValue(value, field) {
    if (value == null || value === '') {
      return null
    }
    const _parsed = this.app.$papa
      .stringToArray(String(value))
      .map((v) => parseInt(v))
    return _.uniq(_parsed)
  }

  matches(rowValue, filterValue, field, fieldType) {
    const parsedValue = this._prepareValue(filterValue)
    return parsedValue === null || _.includes(parsedValue, rowValue?.id)
  }
}

export class SingleSelectIsNoneOfViewFilterType extends SingleSelectIsAnyOfViewFilterType {
  static getType() {
    return 'single_select_is_none_of'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isNoneOf')
  }

  matches(rowValue, filterValue, field, fieldType) {
    const parsedValue = this._prepareValue(filterValue)
    return parsedValue === null || !_.includes(parsedValue, rowValue?.id)
  }
}

export class MultipleSelectHasFilterType extends ViewFilterType {
  static getType() {
    return 'multiple_select_has'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasAnyOf')
  }

  getExample() {
    return '1'
  }

  getInputComponent() {
    return ViewFilterTypeMultipleSelectOptions
  }

  getCompatibleFieldTypes() {
    return [
      'multiple_select',
      FormulaFieldType.compatibleWithFormulaTypes('multiple_select'),
    ]
  }

  prepareValue(value, field) {
    return (this._prepareValue(value, field) || []).join(',')
  }

  _prepareValue(value, field) {
    if (value == null || value === '') {
      return null
    }
    const _parsed = this.app.$papa
      .stringToArray(String(value))
      .map((v) => parseInt(v))
    return _.uniq(_parsed)
  }

  matches(rowValue, filterValue, field, fieldType) {
    const parsedValue = this._prepareValue(filterValue)
    return (
      parsedValue === null ||
      (rowValue?.length &&
        rowValue.some((opt) => _.includes(parsedValue, opt?.id)))
    )
  }
}

export class MultipleSelectHasNotFilterType extends ViewFilterType {
  static getType() {
    return 'multiple_select_has_not'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasNotAnyOf')
  }

  getExample() {
    return '1'
  }

  getInputComponent() {
    return ViewFilterTypeMultipleSelectOptions
  }

  getCompatibleFieldTypes() {
    return [
      'multiple_select',
      FormulaFieldType.compatibleWithFormulaTypes('multiple_select'),
    ]
  }

  prepareValue(value, field) {
    return (this._prepareValue(value, field) || []).join(',')
  }

  _prepareValue(value, field) {
    if (value == null || value === '') {
      return null
    }
    const _parsed = this.app.$papa
      .stringToArray(String(value))
      .map((v) => parseInt(v))
    return _.uniq(_parsed)
  }

  matches(rowValue, filterValue, field, fieldType) {
    const parsedValue = this._prepareValue(filterValue)
    return (
      parsedValue === null ||
      rowValue?.length === 0 ||
      rowValue.every((opt) => !_.includes(parsedValue, opt?.id))
    )
  }
}

export class MultipleCollaboratorsHasFilterType extends ViewFilterType {
  static getType() {
    return 'multiple_collaborators_has'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.has')
  }

  getExample() {
    return '1'
  }

  getInputComponent() {
    return ViewFilterTypeCollaborators
  }

  getCompatibleFieldTypes() {
    return [
      'multiple_collaborators',
      FormulaFieldType.compatibleWithFormulaTypes('multiple_collaborators'),
    ]
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (!isInteger(filterValue)) {
      return true
    }

    const filterValueId = parseInt(filterValue)
    return rowValue.some((user) => user.id === filterValueId)
  }
}

export class MultipleCollaboratorsHasNotFilterType extends ViewFilterType {
  static getType() {
    return 'multiple_collaborators_has_not'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasNot')
  }

  getExample() {
    return '1'
  }

  getInputComponent() {
    return ViewFilterTypeCollaborators
  }

  getCompatibleFieldTypes() {
    return [
      'multiple_collaborators',
      FormulaFieldType.compatibleWithFormulaTypes('multiple_collaborators'),
    ]
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (!isInteger(filterValue)) {
      return true
    }

    const filterValueId = parseInt(filterValue)
    return !rowValue.some((user) => user.id === filterValueId)
  }
}

export class UserIsFilterType extends ViewFilterType {
  static getType() {
    return 'user_is'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.is')
  }

  getExample() {
    return '1'
  }

  getInputComponent() {
    return ViewFilterTypeCollaborators
  }

  getCompatibleFieldTypes() {
    return ['created_by', 'last_modified_by']
  }

  isAllowedInPublicViews() {
    return false
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (!isInteger(filterValue)) {
      return true
    }

    const filterValueId = parseInt(filterValue)
    return rowValue?.id === filterValueId
  }
}

export class UserIsNotFilterType extends ViewFilterType {
  static getType() {
    return 'user_is_not'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isNot')
  }

  getExample() {
    return '1'
  }

  getInputComponent() {
    return ViewFilterTypeCollaborators
  }

  getCompatibleFieldTypes() {
    return ['created_by', 'last_modified_by']
  }

  isAllowedInPublicViews() {
    return false
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (!isInteger(filterValue)) {
      return true
    }

    const filterValueId = parseInt(filterValue)
    return rowValue?.id !== filterValueId
  }
}

export class BooleanViewFilterType extends ViewFilterType {
  static getType() {
    return 'boolean'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.is')
  }

  getExample() {
    return 'true'
  }

  getInputComponent() {
    return ViewFilterTypeBoolean
  }

  getCompatibleFieldTypes() {
    return ['boolean', FormulaFieldType.compatibleWithFormulaTypes('boolean')]
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (filterValue === null) {
      filterValue = false
    }
    filterValue = trueValues.includes(
      filterValue.toString().toLowerCase().trim()
    )

    if (rowValue === null) {
      rowValue = false
    } else {
      rowValue = trueValues.includes(rowValue.toString().toLowerCase().trim())
    }
    return filterValue ? rowValue : !rowValue
  }
}

export class LinkRowHasFilterType extends ViewFilterType {
  static getType() {
    return 'link_row_has'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.has')
  }

  getExample() {
    return '1'
  }

  getInputComponent() {
    return ViewFilterTypeLinkRow
  }

  getCompatibleFieldTypes() {
    return ['link_row']
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (!isInteger(filterValue)) {
      return true
    }

    const filterValueId = parseInt(filterValue)
    return rowValue.some((relation) => relation.id === filterValueId)
  }
}

export class LinkRowHasNotFilterType extends ViewFilterType {
  static getType() {
    return 'link_row_has_not'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.hasNot')
  }

  getExample() {
    return '1'
  }

  getInputComponent() {
    return ViewFilterTypeLinkRow
  }

  getCompatibleFieldTypes() {
    return ['link_row']
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (!isInteger(filterValue)) {
      return true
    }

    const filterValueId = parseInt(filterValue)
    return !rowValue.some((relation) => relation.id === filterValueId)
  }
}

export class LinkRowContainsFilterType extends ViewFilterType {
  static getType() {
    return 'link_row_contains'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.contains')
  }

  getExample() {
    return 'string'
  }

  getInputComponent() {
    return ViewFilterTypeText
  }

  getCompatibleFieldTypes() {
    return ['link_row']
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (filterValue === '') {
      return true
    }

    return rowValue.some(
      ({ value }) => value.search(new RegExp(filterValue, 'i')) !== -1
    )
  }
}

export class LinkRowNotContainsFilterType extends ViewFilterType {
  static getType() {
    return 'link_row_not_contains'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.containsNot')
  }

  getExample() {
    return 'string'
  }

  getInputComponent() {
    return ViewFilterTypeText
  }

  getCompatibleFieldTypes() {
    return ['link_row']
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (filterValue === '') {
      return true
    }

    return !rowValue.some(
      ({ value }) => value.search(new RegExp(filterValue, 'i')) !== -1
    )
  }
}

export class EmptyViewFilterType extends ViewFilterType {
  static getType() {
    return 'empty'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isEmpty')
  }

  getExample() {
    return ''
  }

  get hasEditableValue() {
    return false
  }

  prepareValue(value) {
    return ''
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
      'boolean',
      'link_row',
      'file',
      'single_select',
      'multiple_select',
      'multiple_collaborators',
      'phone_number',
      'duration',
      'password',
      FormulaFieldType.compatibleWithFormulaTypes(
        'text',
        'char',
        'boolean',
        'date',
        'number',
        'duration',
        'url',
        'single_select',
        'multiple_select',
        'multiple_collaborators',
        FormulaFieldType.arrayOf('single_file'),
        FormulaFieldType.arrayOf('text'),
        FormulaFieldType.arrayOf('char'),
        FormulaFieldType.arrayOf('boolean'),
        FormulaFieldType.arrayOf('date'),
        FormulaFieldType.arrayOf('number'),
        FormulaFieldType.arrayOf('url'),
        FormulaFieldType.arrayOf('single_select'),
        FormulaFieldType.arrayOf('multiple_select'),
        FormulaFieldType.arrayOf('multiple_collaborators'),
        FormulaFieldType.arrayOf('duration')
      ),
    ]
  }

  matches(rowValue, filterValue, field, fieldType) {
    return fieldType.isEmpty(field, rowValue)
  }
}

export class NotEmptyViewFilterType extends ViewFilterType {
  static getType() {
    return 'not_empty'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('viewFilter.isNotEmpty')
  }

  getExample() {
    return ''
  }

  get hasEditableValue() {
    return false
  }

  prepareValue(value) {
    return ''
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
      'boolean',
      'link_row',
      'file',
      'single_select',
      'multiple_select',
      'multiple_collaborators',
      'phone_number',
      'duration',
      'password',
      FormulaFieldType.compatibleWithFormulaTypes(
        'text',
        'char',
        'boolean',
        'date',
        'number',
        'duration',
        'url',
        'single_select',
        'multiple_select',
        'multiple_collaborators',
        FormulaFieldType.arrayOf('single_file'),
        FormulaFieldType.arrayOf('text'),
        FormulaFieldType.arrayOf('char'),
        FormulaFieldType.arrayOf('boolean'),
        FormulaFieldType.arrayOf('date'),
        FormulaFieldType.arrayOf('number'),
        FormulaFieldType.arrayOf('url'),
        FormulaFieldType.arrayOf('single_select'),
        FormulaFieldType.arrayOf('multiple_select'),
        FormulaFieldType.arrayOf('multiple_collaborators'),
        FormulaFieldType.arrayOf('duration')
      ),
    ]
  }

  matches(rowValue, filterValue, field, fieldType) {
    return !fieldType.isEmpty(field, rowValue)
  }
}
