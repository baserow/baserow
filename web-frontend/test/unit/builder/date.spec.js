import {
  generateTimePickerTimes,
  updateDateTime,
} from '@baserow/modules/builder/date'
import { DateOnly } from '@baserow/modules/core/utils/date'

describe('generateTimePickerTimes', () => {
  test('should generate times with HH:mm format', () => {
    const times = generateTimePickerTimes('HH:mm')
    expect(times).toHaveLength(48)
    expect(times[0]).toBe('00:00')
    expect(times[1]).toBe('00:30')
    expect(times[47]).toBe('23:30')
  })

  test('should generate times with h:mm A format', () => {
    const times = generateTimePickerTimes('h:mm A')
    expect(times).toHaveLength(48)
    expect(times[0]).toBe('12:00 AM')
    expect(times[24]).toBe('12:00 PM')
    expect(times[47]).toBe('11:30 PM')
  })
})

describe('updateDateTime', () => {
  const dateFormat = 'YYYY-MM-DD'
  const timeFormat = 'HH:mm'

  describe('with includeTime = true', () => {
    test('returns null when both date and time are empty', () => {
      const result = updateDateTime(
        null,
        null,
        true,
        false,
        dateFormat,
        timeFormat
      )
      expect(result).toBeNull()
    })

    test('returns invalid Date when date is empty and not time update', () => {
      const result = updateDateTime(
        null,
        '10:30',
        true,
        false,
        dateFormat,
        timeFormat
      )
      expect(result).toBeInstanceOf(Date)
      expect(isNaN(result)).toBe(true)
    })

    test('returns invalid Date when time is empty and is time update', () => {
      const result = updateDateTime(
        '2023-12-01',
        null,
        true,
        true,
        dateFormat,
        timeFormat
      )
      expect(result).toBeInstanceOf(Date)
      expect(isNaN(result)).toBe(true)
    })

    test('returns invalid Date when date format is invalid', () => {
      const result = updateDateTime(
        'invalid-date',
        '10:30',
        true,
        false,
        dateFormat,
        timeFormat
      )
      expect(result).toBeInstanceOf(Date)
      expect(isNaN(result)).toBe(true)
    })

    test('returns invalid Date when time format is invalid', () => {
      const result = updateDateTime(
        '2023-12-01',
        'invalid-time',
        true,
        false,
        dateFormat,
        timeFormat
      )
      expect(result).toBeInstanceOf(Date)
      expect(isNaN(result)).toBe(true)
    })

    test('returns valid Date with specified date and time', () => {
      const result = updateDateTime(
        '2023-12-01',
        '14:30',
        true,
        false,
        dateFormat,
        timeFormat
      )
      expect(result).toBeInstanceOf(Date)
      expect(result.getFullYear()).toBe(2023)
      expect(result.getMonth()).toBe(11) // December is month 11
      expect(result.getDate()).toBe(1)
      expect(result.getHours()).toBe(14)
      expect(result.getMinutes()).toBe(30)
      expect(result.getSeconds()).toBe(0)
      expect(result.getMilliseconds()).toBe(0)
    })

    test('uses current hour when time is not provided and not time update', () => {
      const result = updateDateTime(
        '2023-12-01',
        null,
        true,
        false,
        dateFormat,
        timeFormat
      )
      expect(result).toBeInstanceOf(Date)
      expect(result.getMinutes()).toBe(0)
      expect(result.getSeconds()).toBe(0)
    })
  })

  describe('with includeTime = false', () => {
    test('returns null when date is empty', () => {
      const result = updateDateTime(
        null,
        '10:30',
        false,
        false,
        dateFormat,
        timeFormat
      )
      expect(result).toBeNull()
    })

    test('returns invalid DateOnly when date format is invalid', () => {
      const result = updateDateTime(
        'invalid-date',
        '10:30',
        false,
        false,
        dateFormat,
        timeFormat
      )
      expect(result).toBeInstanceOf(DateOnly)
      expect(isNaN(result)).toBe(true)
    })

    test('returns valid DateOnly with specified date', () => {
      const result = updateDateTime(
        '2023-12-01',
        '10:30',
        false,
        false,
        dateFormat,
        timeFormat
      )
      expect(result).toBeInstanceOf(DateOnly)
      expect(result.getFullYear()).toBe(2023)
      expect(result.getMonth()).toBe(11)
      expect(result.getDate()).toBe(1)
    })
  })
})
