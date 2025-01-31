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

export const DateFilterOperators = {
  TODAY: { value: 'today', stringKey: 'viewFilter.today' },
  YESTERDAY: { value: 'yesterday', stringKey: 'viewFilter.yesterday' },
  TOMORROW: { value: 'tomorrow', stringKey: 'viewFilter.tomorrow' },
  ONE_WEEK_AGO: { value: 'one_week_ago', stringKey: 'viewFilter.oneWeekAgo' },
  THIS_WEEK: { value: 'this_week', stringKey: 'viewFilter.thisWeek' },
  NEXT_WEEK: { value: 'next_week', stringKey: 'viewFilter.nextWeek' },
  ONE_MONTH_AGO: {
    value: 'one_month_ago',
    stringKey: 'viewFilter.oneMonthAgo',
  },
  THIS_MONTH: { value: 'this_month', stringKey: 'viewFilter.thisMonth' },
  NEXT_MONTH: { value: 'next_month', stringKey: 'viewFilter.nextMonth' },
  ONE_YEAR_AGO: { value: 'one_year_ago', stringKey: 'viewFilter.oneYearAgo' },
  THIS_YEAR: { value: 'this_year', stringKey: 'viewFilter.thisYear' },
  NEXT_YEAR: { value: 'next_year', stringKey: 'viewFilter.nextYear' },
  NR_DAYS_AGO: {
    value: 'nr_days_ago',
    stringKey: 'viewFilter.nrDaysAgo',
    hasNrInputValue: true,
  },
  NR_DAYS_FROM_NOW: {
    value: 'nr_days_from_now',
    stringKey: 'viewFilter.nrDaysFromNow',
    hasNrInputValue: true,
  },
  NR_WEEKS_AGO: {
    value: 'nr_weeks_ago',
    stringKey: 'viewFilter.nrWeeksAgo',
    hasNrInputValue: true,
  },
  NR_WEEKS_FROM_NOW: {
    value: 'nr_weeks_from_now',
    stringKey: 'viewFilter.nrWeeksFromNow',
    hasNrInputValue: true,
  },
  NR_MONTHS_AGO: {
    value: 'nr_months_ago',
    stringKey: 'viewFilter.nrMonthsAgo',
    hasNrInputValue: true,
  },
  NR_MONTHS_FROM_NOW: {
    value: 'nr_months_from_now',
    stringKey: 'viewFilter.nrMonthsFromNow',
    hasNrInputValue: true,
  },
  NR_YEARS_AGO: {
    value: 'nr_years_ago',
    stringKey: 'viewFilter.nrYearsAgo',
    hasNrInputValue: true,
  },
  NR_YEARS_FROM_NOW: {
    value: 'nr_years_from_now',
    stringKey: 'viewFilter.nrYearsFromNow',
    hasNrInputValue: true,
  },
  EXACT_DATE: {
    value: 'exact_date',
    stringKey: 'viewFilter.exactDate',
    hasDateInputValue: true,
  },
}

const parseFilterValueAsDate = (
  filterValue,
  timezone = null,
  dateFormat = 'YYYY-MM-DD'
) => {
  const filterDate = moment.utc(filterValue, dateFormat, true)
  if (!filterDate.isValid()) {
    throw new Error('Invalid date format')
  } else if (timezone) {
    filterDate.tz(timezone, true)
  }
  return filterDate
}

const parseFilterValueAsNumber = (filterValue) => {
  try {
    return parseInt(filterValue)
  } catch {
    return null
  }
}

// Please be aware that momentjs modifies filterDate in place, so
// make sure to clone it before modifying it.
export const DATE_FILTER_OPERATOR_BOUNDS = {
  [DateFilterOperators.TODAY.value]: (filterDate) => [
    filterDate.startOf('day'),
    filterDate.clone().add(1, 'days'),
  ],
  [DateFilterOperators.YESTERDAY.value]: (filterDate) => [
    filterDate.subtract(1, 'days').startOf('day'),
    filterDate.clone().add(1, 'days'),
  ],
  [DateFilterOperators.TOMORROW.value]: (filterDate) => [
    filterDate.add(1, 'days').startOf('day'),
    filterDate.clone().add(1, 'days'),
  ],
  [DateFilterOperators.ONE_WEEK_AGO.value]: (filterDate) => [
    filterDate.subtract(1, 'weeks').startOf('week').add(1, 'days'), // Start of the week is Sunday, so add 1 day to get Monday.
    filterDate.clone().add(1, 'weeks'),
  ],
  [DateFilterOperators.ONE_MONTH_AGO.value]: (filterDate) => [
    filterDate.subtract(1, 'months').startOf('month'),
    filterDate.clone().add(1, 'months'),
  ],
  [DateFilterOperators.ONE_YEAR_AGO.value]: (filterDate) => [
    filterDate.subtract(1, 'years').startOf('year'),
    filterDate.clone().add(1, 'year'),
  ],
  [DateFilterOperators.THIS_WEEK.value]: (filterDate) => [
    filterDate.startOf('week').add(1, 'days'), // Start of the week is Sunday, so add 1 day to get Monday.
    filterDate.clone().add(1, 'week'),
  ],
  [DateFilterOperators.THIS_MONTH.value]: (filterDate) => [
    filterDate.startOf('month'),
    filterDate.clone().add(1, 'months'),
  ],
  [DateFilterOperators.THIS_YEAR.value]: (filterDate) => [
    filterDate.startOf('year'),
    filterDate.clone().add(1, 'years'),
  ],
  [DateFilterOperators.NEXT_WEEK.value]: (filterDate) => [
    filterDate.add(1, 'weeks').startOf('week').add(1, 'days'), // Start of the week is Sunday, so add 1 day to get Monday.
    filterDate.clone().add(1, 'week'),
  ],
  [DateFilterOperators.NEXT_MONTH.value]: (filterDate) => [
    filterDate.add(1, 'months').startOf('month'),
    filterDate.clone().add(1, 'months'),
  ],
  [DateFilterOperators.NEXT_YEAR.value]: (filterDate) => [
    filterDate.add(1, 'years').startOf('year'),
    filterDate.clone().add(1, 'years'),
  ],
  [DateFilterOperators.NR_DAYS_AGO.value]: (filterDate) => [
    filterDate.startOf('day'),
    filterDate.clone().add(1, 'days'),
  ],
  [DateFilterOperators.NR_WEEKS_AGO.value]: (filterDate) => [
    filterDate.startOf('week').add(1, 'days'), // Start of the week is Sunday, so add 1 day to get Monday.
    filterDate.clone().add(1, 'weeks'),
  ],
  [DateFilterOperators.NR_MONTHS_AGO.value]: (filterDate) => [
    filterDate.startOf('month'),
    filterDate.clone().add(1, 'months'),
  ],
  [DateFilterOperators.NR_YEARS_AGO.value]: (filterDate) => [
    filterDate.startOf('year'),
    filterDate.clone().add(1, 'years'),
  ],
  [DateFilterOperators.NR_DAYS_FROM_NOW.value]: (filterDate) => [
    filterDate.startOf('day'),
    filterDate.clone().add(1, 'days'),
  ],
  [DateFilterOperators.NR_WEEKS_FROM_NOW.value]: (filterDate) => [
    filterDate.startOf('week').add(1, 'days'), // Start of the week is Sunday, so add 1 day to get Monday.
    filterDate.clone().add(1, 'weeks'),
  ],
  [DateFilterOperators.NR_MONTHS_FROM_NOW.value]: (filterDate) => [
    filterDate.startOf('month'),
    filterDate.clone().add(1, 'months'),
  ],
  [DateFilterOperators.NR_YEARS_FROM_NOW.value]: (filterDate) => [
    filterDate.startOf('year'),
    filterDate.clone().add(1, 'years'),
  ],
  [DateFilterOperators.EXACT_DATE.value]: (filterDate) => [
    filterDate.startOf('day'),
    filterDate.clone().add(1, 'days'),
  ],
}

export const DATE_FILTER_OPERATOR_DELTA_MAP = {
  [DateFilterOperators.EXACT_DATE.value]: (
    filterDate,
    filterValue,
    timezone
  ) => {
    return parseFilterValueAsDate(filterValue, timezone)
  },
  // days
  [DateFilterOperators.NR_DAYS_AGO.value]: (filterDate, filterValue) => {
    return filterDate.subtract(parseFilterValueAsNumber(filterValue), 'days')
  },
  [DateFilterOperators.NR_DAYS_FROM_NOW.value]: (filterDate, filterValue) => {
    return filterDate.add(parseFilterValueAsNumber(filterValue), 'days')
  },
  // weeks
  [DateFilterOperators.NR_WEEKS_AGO.value]: (filterDate, filterValue) => {
    return filterDate.subtract(parseFilterValueAsNumber(filterValue), 'weeks')
  },
  [DateFilterOperators.NR_WEEKS_FROM_NOW.value]: (filterDate, filterValue) => {
    return filterDate.add(parseFilterValueAsNumber(filterValue), 'weeks')
  },
  // months
  [DateFilterOperators.NR_MONTHS_AGO.value]: (filterDate, filterValue) => {
    return filterDate.subtract(parseFilterValueAsNumber(filterValue), 'months')
  },
  [DateFilterOperators.NR_MONTHS_FROM_NOW.value]: (filterDate, filterValue) => {
    return filterDate.add(parseFilterValueAsNumber(filterValue), 'months')
  },
  // years
  [DateFilterOperators.NR_YEARS_AGO.value]: (filterDate, filterValue) => {
    return filterDate.subtract(parseFilterValueAsNumber(filterValue), 'years')
  },
  [DateFilterOperators.NR_YEARS_FROM_NOW.value]: (filterDate, filterValue) => {
    return filterDate.add(parseFilterValueAsNumber(filterValue), 'years')
  },
}
