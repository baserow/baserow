import moment from '@baserow/modules/core/moment'
import { DateOnly } from '@baserow/modules/core/utils/date'
/**
 * Generate a list of times for the time picker, spaced 30 min apart.
 * @param {string} timeFormat - The format for the time strings (e.g., 'HH:mm').
 * @returns {string[]} - An array of formatted time strings.
 */
export function generateTimePickerTimes(timeFormat) {
  const numberOfHalfHoursInADay = 24 * 2
  return Array.from({ length: numberOfHalfHoursInADay }, (_, i) =>
    moment()
      .startOf('day')
      .add(i * 30, 'minutes')
      .format(timeFormat)
  )
}

/**
 * Updates and validates date/time input based on provided parameters.
 *
 * @param {string|null} date - Date string to parse
 * @param {string|null} time - Time string to parse
 * @param {boolean} includeTime - Whether to include time in the result
 * @param {boolean} isTimeUpdate - Whether this is a time-specific update
 * @param {string} dateFormat - Format string for parsing the date
 * @param {string} timeFormat - Format string for parsing the time
 * @returns {Date|DateOnly|null} Parsed date/time object, DateOnly object, or null
 */
export function updateDateTime(
  date,
  time,
  includeTime,
  isTimeUpdate,
  dateFormat,
  timeFormat
) {
  if (includeTime) {
    if (!date && !time) {
      // We return a null value as the user cleaned both inputs
      return null
    }

    if (!date && !isTimeUpdate) {
      return new Date(NaN)
    }

    if (!time && isTimeUpdate) {
      return new Date(NaN)
    }

    const dateMoment = date ? moment(date, dateFormat, true) : moment()

    if (!dateMoment.isValid()) {
      // Date can't be parsed we return an invalid date
      return new Date(NaN)
    }

    const timeMoment = time
      ? moment(time, timeFormat, true)
      : moment().startOf('hour')

    if (!timeMoment.isValid()) {
      // Date can't be parsed we return an invalid date
      return new Date(NaN)
    }

    // Use currently defined time
    dateMoment
      .hour(timeMoment.hours())
      .minute(timeMoment.minutes())
      .second(0)
      .millisecond(0)

    return dateMoment.toDate()
  } else {
    if (!date) {
      // We just cleared the input
      return null
    }

    const dateMoment = moment(date, dateFormat, true)

    if (!dateMoment.isValid()) {
      return new DateOnly(NaN)
    }

    return new DateOnly(dateMoment.toDate())
  }
}

/**
 * Parses a date string value to update the calendar component.
 * @param {string} value - The string date value from the input.
 * @param {string} dateFormat - The format of the date input.
 * @returns {Date|null} - A JS Date object for the calendar or null if invalid.
 */
export function parseDateForCalendar(value, dateFormat) {
  if (!value) {
    return null
  }
  const parsedDate = moment.utc(value, dateFormat, true) // Strict parsing
  return parsedDate.isValid() ? parsedDate.toDate() : null
}
