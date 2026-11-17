import moment from '@baserow/modules/core/moment'
import {
  describeSchedule,
  formatRunTime,
  getAllowedIntervals,
  getNewScheduleValues,
  getNextRun,
} from '@baserow_enterprise/utils/automaticSnapshots'

const t = (key, params) => (params ? `${key} ${JSON.stringify(params)}` : key)

const schedule = (values) => ({
  interval: 'DAY',
  timezone: 'UTC',
  minute: 0,
  hour: 2,
  day_of_week: 0,
  day_of_month: 1,
  ...values,
})

describe('automatic snapshot utils', () => {
  test('only offers intervals allowed by the minimum', () => {
    expect(getAllowedIntervals(60)).toEqual(['HOUR', 'DAY', 'WEEK', 'MONTH'])
    expect(getAllowedIntervals(5)).toEqual([
      'MINUTE',
      'HOUR',
      'DAY',
      'WEEK',
      'MONTH',
    ])
    expect(getAllowedIntervals(1440)).toEqual(['DAY', 'WEEK', 'MONTH'])
  })

  test('a new schedule runs daily unless that is too often', () => {
    expect(getNewScheduleValues(60, 'Europe/Amsterdam')).toMatchObject({
      interval: 'DAY',
      timezone: 'Europe/Amsterdam',
      hour: 0,
      minute: 0,
      enabled: true,
    })
    expect(getNewScheduleValues(20160, 'UTC').interval).toBe('MONTH')
  })

  test('describes when a schedule runs', () => {
    expect(describeSchedule(schedule({ minute: 5 }), t)).toBe(
      'automaticSnapshots.everyDay {"time":"02:05"}'
    )
    expect(describeSchedule(schedule({ interval: 'HOUR', minute: 7 }), t)).toBe(
      'automaticSnapshots.everyHour {"minute":"07"}'
    )
    expect(
      describeSchedule(schedule({ interval: 'MINUTE', minute: 15 }), t)
    ).toBe('automaticSnapshots.everyMinutes {"minutes":15}')
    expect(
      describeSchedule(
        schedule({ interval: 'WEEK', day_of_week: 2, hour: 9, minute: 30 }),
        t
      )
    ).toBe(
      'automaticSnapshots.everyWeek {"day":"common.wednesday","time":"09:30"}'
    )
  })

  test('calculates the next run like the backend', () => {
    // Wednesday 4 November 2026, 15:00 UTC.
    const from = moment.utc('2026-11-04T15:00:00Z')
    const next = (values) => getNextRun(schedule(values), from).toISOString()

    expect(next({})).toBe('2026-11-05T02:00:00.000Z')
    expect(next({ hour: 16 })).toBe('2026-11-04T16:00:00.000Z')
    expect(next({ interval: 'HOUR', minute: 30 })).toBe(
      '2026-11-04T15:30:00.000Z'
    )
    expect(next({ interval: 'MINUTE', minute: 15 })).toBe(
      '2026-11-04T15:15:00.000Z'
    )
    // Monday is day 0, so the next one is 9 November.
    expect(next({ interval: 'WEEK', day_of_week: 0 })).toBe(
      '2026-11-09T02:00:00.000Z'
    )
    // The 31st doesn't exist in November, so its last day is used.
    expect(next({ interval: 'MONTH', day_of_month: 31 })).toBe(
      '2026-11-30T02:00:00.000Z'
    )
    expect(next({ interval: 'MONTH', day_of_month: 1 })).toBe(
      '2026-12-01T02:00:00.000Z'
    )
    // A local time is kept in the schedule's timezone.
    expect(next({ timezone: 'Europe/Amsterdam' })).toBe(
      '2026-11-05T01:00:00.000Z'
    )
  })

  test('resolves undefined local times like the backend', () => {
    const next = (values, from) =>
      getNextRun(
        schedule({ timezone: 'Europe/Paris', ...values }),
        moment.utc(from)
      ).toISOString()

    // 02:30 doesn't exist on 29 March 2026, so it moves after the transition.
    expect(next({ hour: 2, minute: 30 }, '2026-03-29T00:30:00Z')).toBe(
      '2026-03-29T01:30:00.000Z'
    )
    // 02:45 happens twice on 25 October 2026, and the first one is used.
    expect(
      next(
        { interval: 'WEEK', day_of_week: 6, hour: 2, minute: 45 },
        '2026-10-24T12:00:00Z'
      )
    ).toBe('2026-10-25T00:45:00.000Z')
  })

  test('formats a run time with its timezone', () => {
    const time = '2026-11-05T07:00:00Z'

    // A time of day is shown in the schedule's timezone.
    expect(
      formatRunTime(schedule({ timezone: 'America/New_York' }), time)
    ).toBe('Thu 5 Nov, 02:00 EST')
    // The other intervals are calculated in UTC.
    expect(
      formatRunTime(
        schedule({ interval: 'HOUR', timezone: 'America/New_York' }),
        time
      )
    ).toBe('Thu 5 Nov, 07:00 UTC')
  })
})
