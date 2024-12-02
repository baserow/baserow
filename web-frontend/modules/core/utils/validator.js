import _ from 'lodash'

import { trueValues, falseValues } from '@baserow/modules/core/utils/constants'
import { DATE_FORMATS } from '@baserow/modules/builder/enums'
import moment from '@baserow/modules/core/moment'

/**
 * Ensures that the value is an integer or can be converted to an integer.
 * @param {number|string} value - The value to ensure as an integer.
 * @returns {number} The value as an integer if conversion is successful.
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
 * Ensures that the value is a positive integer.
 * @param {*} value - The value to ensure is a positive integer.
 * @returns {number} The value as an integer if conversion is successful.
 * @throws {Error} If the value is not a valid integer or convertible to an integer.
 */
export const ensurePositiveInteger = (value) => {
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
    (typeof value === 'object' && _.isEmpty(value))
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
  } else if (typeof value === 'object') {
    return JSON.stringify(value)
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
  if (Array.isArray(value)) {
    return value
  }
  if (typeof value === 'string') {
    return value.split(',').map((item) => item.trim())
  }
  return [value]
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
 * @returns {boolean} The value as a boolean.
 */
export const ensureBoolean = (value) => {
  if (trueValues.includes(value)) {
    return true
  } else if (falseValues.includes(value)) {
    return false
  }
  throw new Error('Value is not a valid boolean or convertible to a boolean.')
}

/**
 * Ensures that the value is a valid datetime or convert it.
 * @param {*} value - The value to ensure as a datetime
 * @param {string} format - The format to use to parse the date.
 * @returns {Date} - The converted value as a Date object.
 * @throws {Error} if `value` is not a valid date representation.
 */
export const ensureDateTime = (value, format = DATE_FORMATS.ISO.format) => {
  const momentObject = moment.utc(value, format)
  if (!momentObject.isValid()) {
    throw new Error('Value is not a valid date')
  }
  return momentObject.toDate()
}
