import {
  getDateInTimezone,
  getMonthlyTimestamps,
  DateOnly,
} from '@baserow/modules/core/utils/date'
import moment from '@baserow/modules/core/moment'

describe('getDateInTimezone', () => {
  test('in UTC', () => {
    const result = getDateInTimezone({
      year: 2022,
      month: 10,
      day: 17,
      timezone: 'utc',
    })

    expect(result.toISOString()).toBe('2022-11-17T00:00:00.000Z')
  })

  test('in a different timezone', () => {
    const result = getDateInTimezone({
      year: 2022,
      month: 10,
      day: 17,
      timezone: 'Asia/Kamchatka',
    })

    expect(result.toISOString()).toBe('2022-11-16T12:00:00.000Z')
  })
})

describe('getMonthlyTimestamps', () => {
  test('get valid timestamps for a date in UTC in march 2023', () => {
    const dateTime = moment.tz('2023-03-15T00:00:00', 'utc')

    const monthlyTimestamps = getMonthlyTimestamps(dateTime)
    const monthlyTimestampsFormatted = {
      firstDayNextMonth: monthlyTimestamps.firstDayNextMonth.toISOString(),
      firstDayPreviousMonth:
        monthlyTimestamps.firstDayPreviousMonth.toISOString(),
      fromTimestamp: monthlyTimestamps.fromTimestamp.toISOString(),
      toTimestamp: monthlyTimestamps.toTimestamp.toISOString(),
      firstMondayDayOfRange: monthlyTimestamps.firstMondayDayOfRange,
      visibleNumberOfDaysFromNextMonth:
        monthlyTimestamps.visibleNumberOfDaysFromNextMonth,
      visibleNumberOfDaysFromPreviousMonth:
        monthlyTimestamps.visibleNumberOfDaysFromPreviousMonth,
    }

    expect(monthlyTimestampsFormatted).toStrictEqual({
      firstDayNextMonth: '2023-04-01T00:00:00.000Z',
      firstDayPreviousMonth: '2023-02-01T00:00:00.000Z',
      fromTimestamp: '2023-02-27T00:00:00.000Z',
      toTimestamp: '2023-04-03T00:00:00.000Z',
      firstMondayDayOfRange: 27,
      visibleNumberOfDaysFromNextMonth: 2,
      visibleNumberOfDaysFromPreviousMonth: 2,
    })
  })

  test('get valid timestamps for a date in UTC in april 2023', () => {
    const dateTime = moment.tz('2023-04-22T00:00:00', 'utc')

    const monthlyTimestamps = getMonthlyTimestamps(dateTime)
    const monthlyTimestampsFormatted = {
      firstDayNextMonth: monthlyTimestamps.firstDayNextMonth.toISOString(),
      firstDayPreviousMonth:
        monthlyTimestamps.firstDayPreviousMonth.toISOString(),
      fromTimestamp: monthlyTimestamps.fromTimestamp.toISOString(),
      toTimestamp: monthlyTimestamps.toTimestamp.toISOString(),
      firstMondayDayOfRange: monthlyTimestamps.firstMondayDayOfRange,
      visibleNumberOfDaysFromNextMonth:
        monthlyTimestamps.visibleNumberOfDaysFromNextMonth,
      visibleNumberOfDaysFromPreviousMonth:
        monthlyTimestamps.visibleNumberOfDaysFromPreviousMonth,
    }

    expect(monthlyTimestampsFormatted).toStrictEqual({
      firstDayNextMonth: '2023-05-01T00:00:00.000Z',
      firstDayPreviousMonth: '2023-03-01T00:00:00.000Z',
      fromTimestamp: '2023-03-27T00:00:00.000Z',
      toTimestamp: '2023-05-01T00:00:00.000Z',
      firstMondayDayOfRange: 27,
      visibleNumberOfDaysFromNextMonth: 0,
      visibleNumberOfDaysFromPreviousMonth: 5,
    })
  })

  test('get valid timestamps for a date in UTC in may 2023', () => {
    const dateTime = moment.tz('2023-05-22T00:00:00', 'utc')

    const monthlyTimestamps = getMonthlyTimestamps(dateTime)
    const monthlyTimestampsFormatted = {
      firstDayNextMonth: monthlyTimestamps.firstDayNextMonth.toISOString(),
      firstDayPreviousMonth:
        monthlyTimestamps.firstDayPreviousMonth.toISOString(),
      fromTimestamp: monthlyTimestamps.fromTimestamp.toISOString(),
      toTimestamp: monthlyTimestamps.toTimestamp.toISOString(),
      firstMondayDayOfRange: monthlyTimestamps.firstMondayDayOfRange,
      visibleNumberOfDaysFromNextMonth:
        monthlyTimestamps.visibleNumberOfDaysFromNextMonth,
      visibleNumberOfDaysFromPreviousMonth:
        monthlyTimestamps.visibleNumberOfDaysFromPreviousMonth,
    }

    expect(monthlyTimestampsFormatted).toStrictEqual({
      firstDayNextMonth: '2023-06-01T00:00:00.000Z',
      firstDayPreviousMonth: '2023-04-01T00:00:00.000Z',
      fromTimestamp: '2023-05-01T00:00:00.000Z',
      toTimestamp: '2023-06-05T00:00:00.000Z',
      firstMondayDayOfRange: 1,
      visibleNumberOfDaysFromNextMonth: 4,
      visibleNumberOfDaysFromPreviousMonth: 0,
    })
  })
})

describe('DateOnly', () => {
  test('constructor with no arguments creates today at start of day', () => {
    const dateOnly = new DateOnly()
    const today = new Date()
    expect(dateOnly.getFullYear()).toBe(today.getFullYear())
    expect(dateOnly.getMonth()).toBe(today.getMonth())
    expect(dateOnly.getDate()).toBe(today.getDate())
    expect(dateOnly.getHours()).toBe(0)
    expect(dateOnly.getMinutes()).toBe(0)
    expect(dateOnly.getSeconds()).toBe(0)
    expect(dateOnly.getMilliseconds()).toBe(0)
  })

  test('constructor with date string', () => {
    const dateOnly = new DateOnly('2023-12-25')
    expect(dateOnly.getFullYear()).toBe(2023)
    expect(dateOnly.getMonth()).toBe(11) // December is month 11
    expect(dateOnly.getDate()).toBe(25)
    expect(dateOnly.getHours()).toBe(0)
  })

  test('constructor with Date object', () => {
    const date = new Date('2023-12-25T15:30:45')
    const dateOnly = new DateOnly(date)
    expect(dateOnly.getFullYear()).toBe(2023)
    expect(dateOnly.getMonth()).toBe(11)
    expect(dateOnly.getDate()).toBe(25)
    expect(dateOnly.getHours()).toBe(0)
  })

  test('constructor with multiple arguments', () => {
    const dateOnly = new DateOnly('2023-12-25 10:42', 'YYYY-MM-DD HH:mm', true)
    expect(dateOnly.getFullYear()).toBe(2023)
    expect(dateOnly.getMonth()).toBe(11)
    expect(dateOnly.getDate()).toBe(25)
    expect(dateOnly.getHours()).toBe(0)
    expect(dateOnly.getMinutes()).toBe(0)
  })

  test('constructor with invalid date', () => {
    const dateOnly = new DateOnly('invalid-date')
    expect(dateOnly.toString()).toBe('Invalid Date')
    expect(dateOnly.toJSON()).toBe('Invalid Date')
  })

  test('time setter methods return this and do not change time', () => {
    const dateOnly = new DateOnly('2023-12-25')

    expect(dateOnly.setHours(10)).toBe(dateOnly)
    expect(dateOnly.setMinutes(30)).toBe(dateOnly)
    expect(dateOnly.setSeconds(45)).toBe(dateOnly)
    expect(dateOnly.setMilliseconds(500)).toBe(dateOnly)

    expect(dateOnly.getHours()).toBe(0)
    expect(dateOnly.getMinutes()).toBe(0)
    expect(dateOnly.getSeconds()).toBe(0)
    expect(dateOnly.getMilliseconds()).toBe(0)
  })

  test('time getter methods always return 0', () => {
    const dateOnly = new DateOnly('2023-12-25')
    expect(dateOnly.getHours()).toBe(0)
    expect(dateOnly.getMinutes()).toBe(0)
    expect(dateOnly.getSeconds()).toBe(0)
    expect(dateOnly.getMilliseconds()).toBe(0)
  })

  test('toString returns YYYY-MM-DD format', () => {
    const dateOnly = new DateOnly('2023-12-25')
    expect(dateOnly.toString()).toBe('2023-12-25')
  })

  test('toJSON returns same as toString', () => {
    const dateOnly = new DateOnly('2023-12-25')
    expect(dateOnly.toJSON()).toBe(dateOnly.toString())
    expect(dateOnly.toJSON()).toBe('2023-12-25')
  })

  test('invalid date toString and toJSON', () => {
    const dateOnly = new DateOnly('not-a-date')
    expect(dateOnly.toString()).toBe('Invalid Date')
    expect(dateOnly.toJSON()).toBe('Invalid Date')
  })

  test('inherits from Date', () => {
    const dateOnly = new DateOnly('2023-12-25')
    expect(dateOnly instanceof Date).toBe(true)
    expect(dateOnly instanceof DateOnly).toBe(true)
  })

  test('date methods still work', () => {
    const dateOnly = new DateOnly('2023-12-25')
    expect(dateOnly.getFullYear()).toBe(2023)
    expect(dateOnly.getMonth()).toBe(11)
    expect(dateOnly.getDate()).toBe(25)
    expect(dateOnly.getDay()).toBe(1) // Monday
  })
})
