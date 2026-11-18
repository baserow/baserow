import moment from '@baserow/modules/core/moment'

// The shortest length, in minutes, of each interval. A month is at least 28 days.
const INTERVAL_MINIMUM_MINUTES = {
  HOUR: 60,
  DAY: 60 * 24,
  WEEK: 60 * 24 * 7,
  MONTH: 60 * 24 * 28,
}

// The intervals that run at a time of day, so they depend on the timezone.
export const LOCAL_TIME_INTERVALS = ['DAY', 'WEEK', 'MONTH']

/**
 * Returns the intervals a schedule can use, given the shortest interval in minutes
 * the instance allows. The "every N minutes" interval is only offered when the
 * minimum is below an hour.
 */
export function getAllowedIntervals(minIntervalMinutes) {
  const intervals = minIntervalMinutes < 60 ? ['MINUTE'] : []
  return intervals.concat(
    Object.entries(INTERVAL_MINIMUM_MINUTES)
      .filter(([, minutes]) => minutes >= minIntervalMinutes)
      .map(([interval]) => interval)
  )
}

/**
 * The values a new schedule starts with: every day at the current time in the
 * user's timezone. When daily isn't allowed, the first allowed interval is used.
 */
export function getNewScheduleValues(
  minIntervalMinutes,
  timezone,
  now = moment()
) {
  const intervals = getAllowedIntervals(minIntervalMinutes)
  const interval = intervals.includes('DAY') ? 'DAY' : intervals[0]
  // Starts at the current time, so schedules set up by different people are
  // spread over the day instead of all running at midnight.
  const local = moment.tz(now, timezone)
  return {
    enabled: true,
    interval,
    timezone,
    minute: interval === 'MINUTE' ? minIntervalMinutes : local.minutes(),
    hour: local.hours(),
    day_of_week: 0,
    day_of_month: 1,
  }
}

/**
 * Returns the values of an existing schedule that the form and the API accept.
 */
export function getScheduleValues(schedule) {
  return {
    enabled: schedule.enabled,
    interval: schedule.interval,
    timezone: schedule.timezone,
    minute: schedule.minute,
    hour: schedule.hour,
    day_of_week: schedule.day_of_week,
    day_of_month: schedule.day_of_month,
  }
}

function pad(value) {
  return String(value).padStart(2, '0')
}

const WEEKDAY_KEYS = [
  'common.monday',
  'common.tuesday',
  'common.wednesday',
  'common.thursday',
  'common.friday',
  'common.saturday',
  'common.sunday',
]

/**
 * Describes when a schedule runs, without its timezone, for example
 * "Every day at 02:00".
 */
export function describeSchedule(schedule, t) {
  const time = `${pad(schedule.hour)}:${pad(schedule.minute)}`
  switch (schedule.interval) {
    case 'MINUTE':
      return t('automaticSnapshots.everyMinutes', { minutes: schedule.minute })
    case 'HOUR':
      return t('automaticSnapshots.everyHour', { minute: pad(schedule.minute) })
    case 'DAY':
      return t('automaticSnapshots.everyDay', { time })
    case 'WEEK':
      return t('automaticSnapshots.everyWeek', {
        day: t(WEEKDAY_KEYS[schedule.day_of_week]),
        time,
      })
    case 'MONTH':
      return t('automaticSnapshots.everyMonth', {
        day: schedule.day_of_month,
        time,
      })
    default:
      return ''
  }
}

/**
 * Formats a run time of a schedule with its timezone. Runs at a time of day are
 * shown in the schedule's timezone, so they match its description. The other runs
 * are calculated in UTC, so they're shown in UTC.
 */
export function formatRunTime(schedule, time, format = 'ddd D MMM, HH:mm') {
  const zone = LOCAL_TIME_INTERVALS.includes(schedule.interval)
    ? schedule.timezone
    : 'UTC'
  return moment.utc(time).tz(zone).format(`${format} z`)
}

/**
 * Calculates when a schedule runs next, after `from`. It mirrors the backend's
 * `calculate_next_periodic_run`, so the form can preview the next snapshot before
 * the schedule is saved.
 *
 * @returns {moment.Moment|null} the next run, or null for an unknown interval.
 */
export function getNextRun(schedule, from = moment()) {
  const { interval, minute, hour, day_of_week: dayOfWeek } = schedule
  if (interval === 'MINUTE') {
    return from
      .clone()
      .seconds(0)
      .milliseconds(0)
      .add(minute || 1, 'minutes')
  }
  if (interval === 'HOUR') {
    const next = from.clone().utc().seconds(0).milliseconds(0).minutes(minute)
    return next.isAfter(from) ? next : next.add(1, 'hour')
  }

  const local = from.clone().tz(schedule.timezone).seconds(0).milliseconds(0)
  // Parsing the wall clock time resolves an undefined local time like the backend
  // does: a time in a spring-forward gap moves after the transition, and an
  // ambiguous time in a fall-back overlap is its first occurrence.
  const atTime = (value) =>
    moment.tz(
      `${value.format('YYYY-MM-DD')} ${pad(hour)}:${pad(minute)}`,
      'YYYY-MM-DD HH:mm',
      schedule.timezone
    )
  if (interval === 'DAY') {
    const next = atTime(local)
    return next.isAfter(from) ? next : atTime(local.clone().add(1, 'day'))
  }
  if (interval === 'WEEK') {
    // moment's isoWeekday is 1 for Monday, the backend's day_of_week is 0.
    let next = atTime(local.clone().isoWeekday(dayOfWeek + 1))
    if (!next.isAfter(from)) {
      next = atTime(
        local
          .clone()
          .add(1, 'week')
          .isoWeekday(dayOfWeek + 1)
      )
    }
    return next
  }
  if (interval === 'MONTH') {
    const inMonth = (value) => {
      const day = Math.min(schedule.day_of_month, value.daysInMonth())
      return atTime(value.clone().date(day))
    }
    const next = inMonth(local)
    return next.isAfter(from)
      ? next
      : inMonth(local.clone().date(1).add(1, 'month'))
  }
  return null
}

/**
 * Returns why scheduled runs can't create a snapshot of an application, or `null`
 * when they can: snapshots are turned off, the application keeps none, so runs
 * skip it, or every snapshot it keeps is protected, so runs fail.
 *
 * @param {object} values
 * @param {number|null} values.limit The workspace allowance, `null` without one.
 * @param {number} values.keep The most snapshots the application keeps.
 * @param {number} values.protectedCount How many of its snapshots are protected.
 * @param {string} name The name of the application.
 * @param {Function} t The translation function.
 * @param {boolean} short Whether to return the short version, for a row that
 *   already names the application.
 */
export function getScheduleBlockedWarning(
  { limit, keep, protectedCount },
  name,
  t,
  short = false
) {
  const suffix = short ? 'Short' : ''
  if (limit === 0) {
    return t(`automaticSnapshots.disabledWarning${suffix}`)
  }
  if (keep === 0) {
    return t(`automaticSnapshots.keepsNoneWarning${suffix}`, { name })
  }
  if (protectedCount >= keep) {
    return t(`automaticSnapshots.fullOfProtectedWarning${suffix}`, {
      name,
      count: keep,
    })
  }
  return null
}
