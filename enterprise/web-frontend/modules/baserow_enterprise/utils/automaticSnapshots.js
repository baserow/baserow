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
      return t(
        'automaticSnapshots.everyMinutes',
        { minutes: schedule.minute },
        schedule.minute
      )
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
 * are calculated in UTC, so they're shown in UTC. Without a schedule, for example
 * the last run of an application that no longer has one, the time is shown in the
 * viewer's timezone.
 *
 * @param {object|null} schedule The schedule of the run, if there still is one.
 */
export function formatRunTime(schedule, time, format = 'ddd D MMM, HH:mm') {
  let zone = moment.tz.guess()
  if (schedule) {
    zone = LOCAL_TIME_INTERVALS.includes(schedule.interval)
      ? schedule.timezone
      : 'UTC'
  }
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

  // Like the backend, the next run is found by comparing wall clock times in the
  // schedule's timezone, and only then resolved to the instant it refers to. A UTC
  // moment is used as a naive wall clock time, so DST changes can't affect it.
  const WALL_CLOCK = 'YYYY-MM-DD HH:mm'
  const local = moment.utc(
    from.clone().tz(schedule.timezone).format(WALL_CLOCK),
    WALL_CLOCK
  )
  const atTime = (value) => value.clone().hours(hour).minutes(minute)
  let next
  if (interval === 'DAY') {
    next = atTime(local)
    if (!next.isAfter(local)) {
      next.add(1, 'day')
    }
  } else if (interval === 'WEEK') {
    // moment's isoWeekday is 1 for Monday, the backend's day_of_week is 0.
    let daysAhead = dayOfWeek - (local.isoWeekday() - 1)
    if (daysAhead < 0) {
      daysAhead += 7
    } else if (daysAhead === 0 && !atTime(local).isAfter(local)) {
      daysAhead = 7
    }
    next = atTime(local.clone().add(daysAhead, 'days'))
  } else if (interval === 'MONTH') {
    // Shorter months use their last day.
    const inMonth = (value) =>
      atTime(
        value.clone().date(Math.min(schedule.day_of_month, value.daysInMonth()))
      )
    next = inMonth(local)
    if (!next.isAfter(local)) {
      next = inMonth(local.clone().date(1).add(1, 'month'))
    }
  } else {
    return null
  }
  // Resolving the wall clock time works like the backend: a time in a
  // spring-forward gap moves after the transition, and an ambiguous time in a
  // fall-back overlap is its first occurrence, unless that one already passed.
  const resolved = moment.tz(
    next.format(WALL_CLOCK),
    WALL_CLOCK,
    schedule.timezone
  )
  const secondOccurrence = resolved.clone().add(1, 'hour')
  if (
    !resolved.isAfter(from) &&
    secondOccurrence.clone().tz(schedule.timezone).format(WALL_CLOCK) ===
      next.format(WALL_CLOCK)
  ) {
    return secondOccurrence
  }
  return resolved
}

/**
 * Returns why scheduled runs can't create a snapshot of an application, or `null`
 * when they can: snapshots are turned off, so runs fail, the application has a max
 * of 0, so runs skip it on purpose, or every snapshot it keeps is protected, so
 * runs skip it.
 *
 * @param {object} values
 * @param {number|null} values.limit The workspace allowance, `null` without one.
 * @param {number} values.maxSnapshots The max snapshots of the application.
 * @param {number} values.protectedCount How many of its snapshots are protected.
 * @param {Function} t The translation function.
 * @returns {{message: string, type: string}|null} The message, and the `Alert`
 *   type to show it with. A max of 0 is a choice, not an error, so it's neutral.
 */
export function getScheduleBlockedWarning(
  { limit, maxSnapshots, protectedCount },
  t
) {
  if (limit === 0) {
    return { message: t('automaticSnapshots.blockedDisabled'), type: 'error' }
  }
  if (maxSnapshots === 0) {
    return {
      message: t('automaticSnapshots.blockedMaxSnapshotsZero'),
      type: 'info-neutral',
    }
  }
  if (protectedCount >= maxSnapshots) {
    return {
      message: t('automaticSnapshots.blockedFullOfProtected', {
        count: maxSnapshots,
      }),
      type: 'error',
    }
  }
  return null
}
