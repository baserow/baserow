import moment from '@baserow/modules/core/moment'

/**
 * A wrapper around a `moment.js` date object and its format.
 */
export class FormattedDate {
  /**
   * Create a new `FormattedDate` object.
   * @param {string} date - A 'string' representing a date.
   * @param {?string} format - The date format (e.g, 'DD/MM/YYYY').
   */
  constructor(date, format = null) {
    this.date = moment.utc(date, format || 'YYYY-MM-DD', true)
    this.format = format || 'YYYY-MM-DD'
  }

  /**
   * Return the value of a given unit in this date.
   * @param {string} unit - The name of the unit to retrieve (e.g, 'year')
   * @returns {number} - The value of the retrieved unit.
   */
  get(unit) {
    return this.date.get(unit)
  }

  /**
   * Update a unit of this date with the new value.
   * @param {string} unit - The name of the unit to update (e.g, 'year')
   * @param {number} value - New value to update this date.
   */
  set(unit, value) {
    this.date.set(unit, value)
  }

  /**
   * Return whether this date is valid.
   * @returns {boolean} - `true` if valid, `false` otherwise.
   */
  isValid() {
    return this.date.isValid()
  }

  /**
   * Convert the current date into a javascript Date object.
   * @returns {Date} - The converted date object.
   */
  toDate() {
    return this.date.toDate()
  }

  /**
   * Return a `string` with this date formatted with `format`.
   * @returns {string} - The formatted date.
   */
  toString(format = this.format) {
    return this.date.format(format)
  }

  /**
   * Return a `string` with this date in ISO format.
   * @returns {string} - The date in ISO format.
   */
  toJSON() {
    return this.date.format('YYYY-MM-DD')
  }
}

/**
 * A wrapper around a `moment.js` date and time object and its format.
 */
export class FormattedDateTime {
  /**
   * Create a new `FormattedDateTime` object.
   * @param {string} datetime - A string representing the date and time.
   * @param {?string} format - The date and time format (e.g, 'DD/MM/YYYY HH:mm').
   *                           If not provided it will use ISO 8601 format.
   * @param {?string} timezone - The timezone (e.g, 'Europe/Lisbon').
   *                             If not provided it will try to guess it from
   *                             the locale.
   */
  constructor(datetime, format = null, timezone = null) {
    this.datetime = moment.tz(
      datetime,
      format || moment.ISO_8601,
      true,
      timezone || moment.tz.guess()
    )
    this.format = format || 'YYYY-MM-DD HH:mm'
  }

  /**
   * Return the value of a given unit in this date and time.
   * @param {string} unit - The name of the unit to retrieve (e.g, 'hour')
   * @returns {number} - The value of the retrieved unit.
   */
  get(unit) {
    return this.datetime.get(unit)
  }

  /**
   * Update a unit of this date and time with the new value.
   * @param {string} unit - The name of the unit to update (e.g, 'hour')
   * @param {number} value - New value to update this date and time.
   */
  set(unit, value) {
    this.datetime.set(unit, value)
  }

  /**
   * Return whether this datetime is valid.
   * @returns {boolean} - `true` if valid, `false` otherwise.
   */
  isValid() {
    return this.datetime.isValid()
  }

  /**
   * Convert the current datetime into a javascript Date object.
   * @returns {Date} - The converted date object.
   */
  toDate() {
    return this.datetime.toDate()
  }

  /**
   * Return a `string` with this date and time formatted with `format`.
   * @returns {string} - The formatted date and time.
   */
  toString(format = this.format) {
    return this.datetime.format(format)
  }

  /**
   * Return a `string` with this date and time in ISO format.
   * @returns {string} - The date and time in ISO format.
   */
  toJSON() {
    return this.datetime.toISOString()
  }
}
