import _ from 'lodash'

import { trueValues, falseValues } from '@baserow/modules/core/utils/constants'
import moment from '@baserow/modules/core/moment'
import { DateOnly } from '@baserow/modules/core/utils/date'

const isoRegex = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z?$/
const isoDateFormat = 'YYYY-MM-DD HH:mm:ss'
/**
 * Ensures that the value is a Numeral or can be converted to a numeric value.
 * @param {number|string} value - The value to ensure as a number.
 * @param allowNull {boolean} - Whether to allow null or empty values.
 * @returns {number|null} The value as a Number if conversion is successful.
 * @throws {Error} If the value is not a valid number or convertible to an number.
 */
export const ensureNumeric = (value, { allowNull = false } = {}) => {
  if (allowNull && (value === null || value === '' || value === undefined)) {
    return null
  }
  if (Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string' || value instanceof String) {
    if (/^([-+])?(\d+(\.\d+)?)$/.test(value)) {
      return Number(value)
    }
  }

  throw new Error(
    `Value '${value}' is not a valid number or convertible to a number.`
  )
}

/**
 * Ensures that the value is an integer or can be converted to an integer.
 * @param {number|string} value - The value to ensure as an integer.
 * @param allowNull {boolean} - Whether to allow null or empty values.
 * @returns {number|null} The value as an integer if conversion is successful, null otherwise.
 * @throws {Error} If the value is not a valid integer or convertible to an integer.
 */
export const ensureInteger = (value) => {
  if (Number.isInteger(value)) {
    return value
  }
  if (typeof value === 'string' || value instanceof String) {
    if (/^(-|\+)?(\d+|Infinity)$/.test(value)) {
      return Number(value)
    }
  }
  throw new Error(
    `Value '${value}' is not a valid integer or convertible to an integer.`
  )
}

/**
 * Ensures that the value is a non-negative integer.
 * @param {*} value - The value to ensure is a non-negative integer.
 * @param {Object} options - Configuration options
 * @param {Boolean} [options.allowNull=false] - Whether to return null if value is null
 * @returns {number|null} The value as an integer if conversion is successful,
 * or null if allowNull is true or throwError is false
 * @throws {Error} If the value is not a valid non-negative integer
 */
export const ensurePositiveInteger = (value, { allowNull = false } = {}) => {
  if (allowNull && (value === null || value === '')) {
    return null
  }
  const validInteger = ensureInteger(value)
  if (validInteger < 0) {
    throw new Error('Value is not a positive integer.')
  }
  return validInteger
}
/**
 * Ensures that the value is a string or try to convert it.
 * @param {*} value - The value to ensure as a string.
 * @param {Boolean} allowEmpty - Whether we should throw an error if `value` is empty.
 * @returns {string} The value as a string.
 * @throws {Error} If !allowEmpty and the `value` is empty.
 */
export const ensureString = (value, { allowEmpty = true } = {}) => {
  if (
    value === null ||
    value === undefined ||
    value === '' ||
    (Array.isArray(value) && !value.length) ||
    (typeof value === 'object' && !(value instanceof Date) && _.isEmpty(value))
  ) {
    if (!allowEmpty) {
      throw new Error('A valid String is required.')
    }
    return ''
  }

  if (Array.isArray(value)) {
    // convert item into a string recursively
    const results = value.map((item) => ensureString(item))
    return results.join(',')
  } else if (value instanceof DateOnly) {
    return value.toString()
  } else if (value instanceof Date) {
    if (!isNaN(value)) {
      return moment(value).format(isoDateFormat)
    }
  } else if (typeof value === 'object') {
    // If it's a file we just extract the name
    if (value.__file__) {
      return value.name
    }
    return JSON.stringify(value)
  } else if (typeof value === 'string') {
    // Special case for iso strings. We parse them as dates for better display.
    if (isoRegex.test(value)) {
      const date = moment(value)
      if (date.isValid()) {
        return date.format(isoDateFormat)
      }
    }
  }
  return `${value}`
}

/**
 * Ensures the value is a string or an integer, otherwise tries to
 * convert the value to a string.
 *
 * @param {*} value - The value to ensure as a string or integer.
 * @param {Boolean} allowEmpty - Whether we should throw an error if `value` is empty.
 * @returns {string|number} The value as a string or integer.
 * @throws {Error} If !allowEmpty and the `value` is empty.
 */
export const ensureStringOrInteger = (value, { allowEmpty = true } = {}) => {
  if (Number.isInteger(value)) {
    return value
  }

  return ensureString(value, { allowEmpty })
}

/**
 * Ensure that the value is an array or try to convert it.
 * Strings will be treated as comma separated values.
 * Other data types will be transformed into a single element array.
 *
 * @param {*} value - The value to ensure as an array.
 * @param {Boolean} allowEmpty - Whether we should throw an error if `value` is empty.
 * @returns {any[]} The value as an array.
 * @throws {Error} if !allowEmpty and `value` is empty.
 */
export const ensureArray = (value, { allowEmpty = true } = {}) => {
  if (
    value === null ||
    value === undefined ||
    value === '' ||
    (Array.isArray(value) && !value.length)
  ) {
    if (!allowEmpty) {
      throw new Error('A non empty value is required.')
    }
    return []
  }
  let result
  if (Array.isArray(value)) {
    result = value
  } else if (typeof value === 'string') {
    result = value.split(',').map((item) => item.trim())
  } else {
    result = [value]
  }
  return result
}

/**
 * Ensures that the value is a non-empty string or try to convert it.
 * @param {*} value - The value to ensure as a string, which can't be blank.
 * @returns {string} The value as a string
 * @throws {Error} If `value` is empty.
 */
export const ensureNonEmptyString = (value, options) => {
  return ensureString(value, { ...options, allowEmpty: false })
}

/**
 * Ensures that the value is a boolean or convert it.
 * @param {*} value - The value to ensure as a boolean.
 * @param {boolean} useStrict - Whether to be strict in how the value is interpreted.
 * @returns {boolean} The value as a boolean.
 */
export const ensureBoolean = (value, { useStrict = true } = {}) => {
  if (trueValues.includes(value)) {
    return true
  } else if (falseValues.includes(value)) {
    return false
  }

  if (!useStrict) {
    return Boolean(value)
  }

  throw new Error('Value is not a valid boolean or convertible to a boolean.')
}

/**
 * Ensures that the value is a valid date or convert it.
 * @param {*} value - The value to ensure as a date
 * @returns {DateOnly} - The converted value as a DateOnly object.
 * @throws {Error} if `value` is not a valid date representation.
 */
export const ensureDate = (value, { allowEmpty = true } = {}) => {
  if (value === null || value === undefined || value === '') {
    if (!allowEmpty) {
      throw new Error('A non empty value is required.')
    }
    return null
  }

  const result = new DateOnly(value, 'YYYY-MM-DD', true)

  if (isNaN(result)) {
    throw new TypeError('Value is not a valid date or convertible to a date.')
  }

  return result
}

/**
 * Ensures that the value is a valid datetime or convert it.
 * @param {*} value - The value to ensure as a datetime
 * @param {boolean} allowEmpty - Whether to allow empty values.
 * @param {string} format - The format to use to parse the datetime.
 * @returns {Date} - The converted value as a Date object.
 * @throws {Error} if `value` is not a valid date representation.
 */
export const ensureDateTime = (
  value,
  { allowEmpty = true, format = moment.ISO_8601, useStrict = true } = {}
) => {
  if (value === null || value === undefined || value === '') {
    if (!allowEmpty) {
      throw new Error('A non empty value is required.')
    }
    return null
  }
  if (value instanceof Date) {
    return value
  } else {
    const parsed = format ? moment(value, format, useStrict) : moment(value)
    if (!parsed.isValid()) {
      throw new TypeError(
        'Value is not a valid datetime or convertible to a datetime.'
      )
    }
    return parsed.toDate()
  }
}

/**
 * Ensures that the value is a valid object or convert it.
 * @param {*} value - The value to ensure as an object
 * @returns {Object} - The converted value as an object.
 * @throws {Error} if `value` is not convertable to an object.
 */
export const ensureObject = (value) => {
  // Return early if it's an object
  if (value instanceof Object) {
    return value
  }

  if (value === null || value === undefined) {
    throw new TypeError(
      'Value is not a valid object or convertible to an object.'
    )
  }

  // If it's a string, try to parse it as JSON
  if (typeof value === 'string') {
    try {
      return JSON.parse(value)
    } catch {
      throw new TypeError('Value is not a valid JSON.')
    }
  }

  throw new TypeError(
    'Value is not a valid object or convertible to an object.'
  )
}
