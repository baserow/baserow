import moment from '@baserow/modules/core/moment'

const dateMapping = {
  EU: {
    momentFormat: 'DD/MM/YYYY',
    humanFormat: 'dd/mm/yyyy',
  },
  US: {
    momentFormat: 'MM/DD/YYYY',
    humanFormat: 'mm/dd/yyyy',
  },
  ISO: {
    momentFormat: 'YYYY-MM-DD',
    humanFormat: 'yyyy-mm-dd',
  },
}

const timeMapping = {
  12: {
    momentFormat: 'hh:mm A',
    humanFormat: 'hh:mm AM',
  },
  24: {
    momentFormat: 'HH:mm',
    humanFormat: 'hh:mm',
  },
}

export const getDateMomentFormat = (type) => {
  if (!Object.prototype.hasOwnProperty.call(dateMapping, type)) {
    throw new Error(`${type} wasn't found in the date mapping.`)
  }
  return dateMapping[type].momentFormat
}

export const getTimeMomentFormat = (type) => {
  if (!Object.prototype.hasOwnProperty.call(timeMapping, type)) {
    throw new Error(`${type} wasn't found in the time mapping.`)
  }
  return timeMapping[type].momentFormat
}

export const getDateHumanReadableFormat = (type) => {
  if (!Object.prototype.hasOwnProperty.call(dateMapping, type)) {
    throw new Error(`${type} wasn't found in the date mapping.`)
  }
  return dateMapping[type].humanFormat
}

export const getTimeHumanReadableFormat = (type) => {
  if (!Object.prototype.hasOwnProperty.call(timeMapping, type)) {
    throw new Error(`${type} wasn't found in the time mapping.`)
  }
  return timeMapping[type].humanFormat
}

/**
 * Returns the timezone for a given field. If the field doesn't have a timezone
 * set, the timezone of the user is returned.
 *
 * @param {Object} field The field object
 * @param {boolean} guess Whether or not to try guess the users timezone
 * @returns {String} The timezone for the field
 * @example
 * getFieldTimezone({ date_include_time: true, date_force_timezone: 'Europe/Amsterdam' }) // => 'Europe/Amsterdam'
 * getFieldTimezone({ date_include_time: false }) // => 'UTC'
 */
export const getFieldTimezone = (field, guess = true) => {
  return field.date_include_time
    ? field.date_force_timezone ||
        (guess && !process.server && moment.tz.guess())
    : null
}

/**
 * Returns the timezone abbreviation for a given field and value.
 * If the value is null or undefined and force=false, an empty string is returned.
 *
 * @param {Object} field The field object
 * @param {String | moment} value The value to parse into a moment object
 * @param {Object} options
 * @param {String} options.format The format to parse the value with
 * @param {Boolean} options.replace Whether to replace the timezone or not
 */
export const getCellTimezoneAbbr = (
  field,
  value,
  { format = 'z', force = false } = {}
) => {
  if (!force && (value === null || value === undefined)) {
    return ''
  }
  const timezone = getFieldTimezone(field)

  return timezone
    ? moment
        .utc(value || undefined)
        .tz(timezone)
        .format(format)
    : 'UTC'
}

export const DATE_FILTER_VALUE_SEPARATOR = '?'

/**
 * Splits the timezone and the filter value from a filter value.
 *
 * @param {*} value  The filter value
 * @param {*} separator  The separator between the timezone and the filter value
 * @returns {Array}  An array with the timezone and the filter value
 */
export const splitTimezoneAndFilterValue = (
  value,
  separator = DATE_FILTER_VALUE_SEPARATOR
) => {
  let timezone = null
  let filterValue

  if (value.includes(separator)) {
    // if the filter value already contains a timezone, use it
    ;[timezone, filterValue] = value.split(separator)
  } else {
    // fallback for values before timezone was added to the filter value
    filterValue = value
  }
  timezone = moment.tz.zone(timezone) ? timezone : null
  return [timezone, filterValue]
}

/**
 * Split the filter value for multi-step date filters.
 * @param {String} value The filter value
 * @param {String} separator The separator between the timezone, the filter value and the operator
 * @returns {Array} An array with the timezone, the filter value and the operator
 */
export const splitMultiStepDateValue = (
  value,
  separator = DATE_FILTER_VALUE_SEPARATOR
) => {
  const splittedValue = value.split(separator)
  if (splittedValue.length === 3) {
    return splittedValue
  } else if (splittedValue.length === 2) {
    // let's assume the timezone has not been provided
    return [null, splittedValue[0], splittedValue[1]]
  } else {
    return [null, '', '']
  }
}

/**
 * Compares an item with a previous item to determine
 * whether a day separator should be rendered.
 *
 * @param {*} items All items that contains the timestamp property
 * @param {String} prop The name of the property that holds the timestamp
 * @param {Number} index Index at which we need to decide if previous and
 *  next item's datetimes differ
 * @returns {Boolean} Whether the timestamps around the index warrant
 *  rendering a date separator
 */
export const shouldDisplayDateSeparator = (items, prop, index) => {
  if (index === items.length - 1) {
    return true
  }
  const tzone = moment.tz.guess()
  const prevDate = moment.utc(items[index][prop]).tz(tzone)
  const currentDate = moment.utc(items[index + 1][prop]).tz(tzone)
  return !prevDate.isSame(currentDate, 'day')
}

/**
 * Formats output for date separators when separating items based on
 * day (today, yesterday, etc.)
 *
 * @param {moment} timestamp The datetime to format
 * @returns {String} The formatted timestamp
 */
export const formatDateSeparator = (timestamp) => {
  return moment.utc(timestamp).tz(moment.tz.guess()).calendar(null, {
    sameDay: '[Today]',
    lastDay: '[Yesterday]',
    lastWeek: 'LL',
    sameElse: 'LL',
  })
}

/**
 * Prepares a value for a multi-step date filter. It combines the timezone,
 * the filter value and the operator into a single string. It puts the operator
 * at the end to keep the compatibility with the old filter values.
 *
 * @param {String} filterValue The filter value
 * @param {String} timezone The timezone
 * @param {String} operator The date filter operator to use
 * @returns {String} The combined value to send to the backend
 */
export const prepareMultiStepDateValue = (filterValue, timezone, operator) => {
  const sep = DATE_FILTER_VALUE_SEPARATOR
  return `${timezone}${sep}${filterValue}${sep}${operator}`
}
