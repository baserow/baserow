import moment from '@baserow/modules/core/moment'

export class Timedelta {
  constructor(ms) {
    this.ms = ms
  }
}

const INTERVAL_PATTERNS = [
  { regex: /^(\d+)\s+years?$/i, unit: 'days', factor: 365 },
  { regex: /^(\d+)\s+months?$/i, unit: 'days', factor: 30 },
  { regex: /^(\d+)\s+weeks?$/i, unit: 'days', factor: 7 },
  { regex: /^(\d+)\s+days?$/i, unit: 'days', factor: 1 },
  { regex: /^(\d+)\s+hours?$/i, unit: 'hours', factor: 1 },
  { regex: /^(\d+)\s+minutes?$/i, unit: 'minutes', factor: 1 },
  { regex: /^(\d+)\s+seconds?$/i, unit: 'seconds', factor: 1 },
]

const UNIT_TO_MS = {
  days: 24 * 60 * 60 * 1000,
  hours: 60 * 60 * 1000,
  minutes: 60 * 1000,
  seconds: 1000,
}

export function parseIntervalString(value) {
  if (typeof value !== 'string') return null
  for (const { regex, unit, factor } of INTERVAL_PATTERNS) {
    const match = value.trim().match(regex)
    if (match) {
      const amount = parseInt(match[1], 10) * factor
      return new Timedelta(amount * UNIT_TO_MS[unit])
    }
  }
  return null
}

export const getHumanPeriodAgoCount = (dateTime) => {
  const now = moment()
  const d = moment(dateTime)

  const diffYears = now.diff(d, 'years')
  if (diffYears >= 1) {
    return {
      period: 'years',
      count: diffYears,
    }
  }

  const diffMonths = now.diff(d, 'months')
  if (diffMonths >= 1) {
    return {
      period: 'months',
      count: diffMonths,
    }
  }

  const diffDays = now.diff(d, 'days')
  if (diffDays >= 1) {
    return {
      period: 'days',
      count: diffDays,
    }
  }

  const diffHours = now.diff(d, 'hours')
  if (diffHours >= 1) {
    return {
      period: 'hours',
      count: diffHours,
    }
  }

  const diffMinutes = now.diff(d, 'minutes')
  if (diffMinutes >= 1) {
    return {
      period: 'minutes',
      count: diffMinutes,
    }
  }

  const diffSeconds = now.diff(d, 'seconds')
  return {
    period: 'seconds',
    count: diffSeconds,
  }
}

export function getMonthName(dateTime) {
  return moment(dateTime).format('MMMM YYYY')
}

export function getCapitalizedMonthName(dateTime) {
  const name = getMonthName(dateTime)
  return name.charAt(0).toUpperCase() + name.slice(1)
}

/**
 * Returns translated short names for week days
 * starting Monday
 */
export function weekDaysShort() {
  const weekDays = moment.weekdaysShort()
  weekDays.push(weekDays.shift())
  return weekDays
}

/**
 * Helper to construct correct moment datetime representing date in a
 * given timezone.
 *
 * Time is set to 0:0. Months are numbered from 0.
 */
export function getDateInTimezone({ year, month, day, timezone }) {
  return moment.tz(
    {
      year,
      month,
      day,
      hour: 0,
      minute: 0,
      second: 0,
      millisecond: 0,
    },
    timezone
  )
}

/**
 * Given a datetime returns [from and to) timestamps for a monthly calendar
 * view surrounding the provided datetime, including days before and after the
 * datetime's month.
 *
 * @param {moment} dateTime
 */
export function getMonthlyTimestamps(dateTime) {
  const firstDayOfMonth = getDateInTimezone({
    year: dateTime.year(),
    month: dateTime.month(),
    day: 1,
    timezone: dateTime.tz(),
  })
  const firstDayOfMonthWeekday = moment(firstDayOfMonth).isoWeekday()
  const firstDayPreviousMonth = moment(firstDayOfMonth).subtract(1, 'month')
  const visibleNumberOfDaysFromPreviousMonth = firstDayOfMonthWeekday
    ? firstDayOfMonthWeekday - 1
    : 6
  const firstMondayDayOfRange = moment(firstDayOfMonth)
    .subtract(visibleNumberOfDaysFromPreviousMonth, 'day')
    .date()
  const fromTimestamp =
    visibleNumberOfDaysFromPreviousMonth === 0
      ? firstDayOfMonth
      : getDateInTimezone({
          year: firstDayPreviousMonth.year(),
          month: firstDayPreviousMonth.month(),
          day: firstMondayDayOfRange,
          timezone: dateTime.tz(),
        })

  const daysInMonth = dateTime.daysInMonth()
  const lastDayOfMonth = getDateInTimezone({
    year: dateTime.year(),
    month: dateTime.month(),
    day: daysInMonth,
    timezone: dateTime.tz(),
  })
  const lastDayOfMonthWeekday = lastDayOfMonth.isoWeekday()
  const firstDayNextMonth = getDateInTimezone({
    year: dateTime.year(),
    month: dateTime.month(),
    day: 1,
    timezone: dateTime.tz(),
  }).add(1, 'month')
  const visibleNumberOfDaysFromNextMonth = lastDayOfMonthWeekday
    ? 7 - lastDayOfMonthWeekday
    : lastDayOfMonthWeekday
  const toTimestamp = getDateInTimezone({
    year: firstDayNextMonth.year(),
    month: firstDayNextMonth.month(),
    day: visibleNumberOfDaysFromNextMonth + 1,
    timezone: dateTime.tz(),
  })
  return {
    fromTimestamp,
    toTimestamp,
    visibleNumberOfDaysFromNextMonth,
    visibleNumberOfDaysFromPreviousMonth,
    firstMondayDayOfRange,
    firstDayPreviousMonth,
    firstDayNextMonth,
  }
}

export function getUserTimeZone() {
  if (import.meta.server) {
    return 'UTC'
  } else {
    return moment.tz.guess()
  }
}

export class DateOnly extends Date {
  constructor(...args) {
    // We directly give the parameters to moment for flexbility
    const momentDate = moment(...args).startOf('day')

    // Check if moment is invalid
    if (!momentDate.isValid()) {
      super('invalid')
      this._moment = momentDate
      return
    }

    super(momentDate.toDate())
    this._moment = momentDate
  }

  // Override other methods...
  setHours() {
    return this
  }

  setMinutes() {
    return this
  }

  setSeconds() {
    return this
  }

  setMilliseconds() {
    return this
  }

  getHours() {
    return 0
  }

  getMinutes() {
    return 0
  }

  getSeconds() {
    return 0
  }

  getMilliseconds() {
    return 0
  }

  toString() {
    return this._moment.isValid()
      ? this._moment.format('YYYY-MM-DD')
      : 'Invalid Date'
  }

  toJSON() {
    return this.toString()
  }
}
