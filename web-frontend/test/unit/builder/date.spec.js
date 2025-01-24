import { FormattedDate, FormattedDateTime } from '@baserow/modules/builder/date'
import moment from '@baserow/modules/core/moment'

describe('FormattedDate', () => {
  test('constructor', () => {
    const formattedDate = new FormattedDate('', 'DD/MM/YYYY')
    expect(formattedDate.date).toBeInstanceOf(moment)
    expect(formattedDate.format).toBe('DD/MM/YYYY')
  })

  test('constructor default parameter', () => {
    const formattedDate = new FormattedDate('')
    expect(formattedDate.date).toBeInstanceOf(moment)
    expect(formattedDate.format).toBe('YYYY-MM-DD')
  })

  test.each([
    ['1975-04-25', null, true],
    ['1975-25-04', null, false],
    ['1975-04-25', 'YYYY-MM-DD', true],
    ['1975-04-25', 'YYYY-MM', false],
    ['25/04/1975', null, false],
    ['25/04/1975', 'DD/MM/YYYY', true],
    ['04/25/1975', null, false],
    ['04/25/1975', 'MM/DD/YYYY', true],
  ])('isValid %s', (date, format, isValid) => {
    const formattedDate = new FormattedDate(date, format)
    expect(formattedDate.isValid()).toBe(isValid)
  })

  test.each([
    ['1975-04-25', 'YYYY-MM-DD'],
    ['25/04/1975', 'DD/MM/YYYY'],
    ['04/25/1975', 'MM/DD/YYYY'],
  ])('toString %s', (date, format) => {
    const formattedDate = new FormattedDate(date, format)
    expect(formattedDate.toString()).toBe(date)
  })

  test.each([
    ['1975-04-25', null],
    ['1975-04-25', 'YYYY-MM-DD'],
    ['25/04/1975', 'DD/MM/YYYY'],
    ['04/25/1975', 'MM/DD/YYYY'],
  ])('toJSON %s', (date, format) => {
    const formattedDate = new FormattedDate(date, format)
    expect(formattedDate.toJSON()).toBe('1975-04-25')
  })
})

describe('FormattedDateTime', () => {
  test('constructor', () => {
    const formattedDateTime = new FormattedDateTime('', 'DD/MM/YYYY HH:mm')
    expect(formattedDateTime.datetime).toBeInstanceOf(moment)
    expect(formattedDateTime.format).toBe('DD/MM/YYYY HH:mm')
  })

  test('constructor default parameter', () => {
    const formattedDateTime = new FormattedDateTime('')
    expect(formattedDateTime.datetime).toBeInstanceOf(moment)
    expect(formattedDateTime.format).toBe('YYYY-MM-DD HH:mm')
  })

  test.each([
    ['1975-04-25 10:30', null, true],
    ['1975-25-04 10:30', null, false],
    ['1975-04-25 10:30', 'YYYY-MM-DD HH:mm', true],
    ['1975-04-25 10:30', 'YYYY-MM', false],
    ['25/04/1975 10:30', null, false],
    ['25/04/1975 10:30', 'DD/MM/YYYY HH:mm', true],
    ['04/25/1975 10:30', null, false],
    ['04/25/1975 10:30', 'MM/DD/YYYY HH:mm', true],
  ])('isValid %s', (date, format, isValid) => {
    const formattedDate = new FormattedDateTime(date, format)
    expect(formattedDate.isValid()).toBe(isValid)
  })

  test.each([
    ['1975-04-25 10:30', null],
    ['1975-04-25 10:30', 'YYYY-MM-DD HH:mm'],
    ['25/04/1975 10:30', 'DD/MM/YYYY HH:mm'],
    ['04/25/1975 10:30', 'MM/DD/YYYY HH:mm'],
  ])('toJSON %s', (date, format) => {
    const formattedDate = new FormattedDateTime(date, format)
    expect(formattedDate.toJSON()).toBe('1975-04-25T10:30:00.000Z')
  })

  test.each([
    ['1987-09-30 15:00', 'Europe/Lisbon'], // WET = 00:00 UTC
    ['1987-09-30 16:00', 'Europe/London'], // BST = -01:00 UTC
    ['1987-09-30 05:00', 'Pacific/Honolulu'], // HST = -10:00 UTC
    ['1987-10-01 01:00', 'Australia/Sydney'], // AEDT = +10:00 UTC
  ])('timezone', (date, timezone) => {
    const formattedDate = new FormattedDateTime(
      date,
      'YYYY-MM-DD HH:mm',
      timezone
    )
    expect(formattedDate.toJSON()).toBe('1987-09-30T15:00:00.000Z')
  })
})
