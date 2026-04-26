import * as XLSX from 'xlsx'

import {
  ExcelParser,
  stringifyCell,
} from '@baserow/modules/database/utils/excel'

/**
 * Build an in-memory xlsx workbook and return it as a Uint8Array, mirroring
 * what a `<input type="file">` + `FileReader.readAsArrayBuffer` would yield.
 */
function buildWorkbook(sheets) {
  const wb = XLSX.utils.book_new()
  for (const [name, rows] of Object.entries(sheets)) {
    const ws = XLSX.utils.aoa_to_sheet(rows)
    XLSX.utils.book_append_sheet(wb, ws, name)
  }
  return new Uint8Array(XLSX.write(wb, { type: 'array', bookType: 'xlsx' }))
}

describe('ExcelParser', () => {
  test('parses a single-sheet workbook into rows of strings', () => {
    const data = buildWorkbook({
      Sheet1: [
        ['Name', 'Age', 'Active'],
        ['Alice', 30, true],
        ['Bob', 25, false],
      ],
    })
    const parser = new ExcelParser()
    const sheets = parser.parse(data)

    expect(sheets).toEqual(['Sheet1'])
    expect(parser.getSheetRows('Sheet1')).toEqual([
      ['Name', 'Age', 'Active'],
      ['Alice', '30', 'TRUE'],
      ['Bob', '25', 'FALSE'],
    ])
  })

  test('exposes every sheet name in workbook order', () => {
    const data = buildWorkbook({
      Customers: [['Name'], ['Alice']],
      Orders: [['Id'], ['1']],
    })
    const parser = new ExcelParser()

    expect(parser.parse(data)).toEqual(['Customers', 'Orders'])
    expect(parser.getSheetRows('Customers')).toEqual([['Name'], ['Alice']])
    expect(parser.getSheetRows('Orders')).toEqual([['Id'], ['1']])
  })

  test('skips fully empty rows but keeps trailing empty cells', () => {
    const data = buildWorkbook({
      Sheet1: [['a', 'b', 'c'], [], ['x', '', 'z']],
    })
    const parser = new ExcelParser()
    parser.parse(data)

    expect(parser.getSheetRows('Sheet1')).toEqual([
      ['a', 'b', 'c'],
      ['x', '', 'z'],
    ])
  })

  test('formats date cells using their cell format', () => {
    const ws = XLSX.utils.aoa_to_sheet([
      ['When'],
      [new Date(Date.UTC(2026, 3, 26))],
    ])
    // SheetJS uses cell formats to render dates with `raw: false`. Without a
    // format the cell stays a date number, so set one explicitly.
    ws.A2.z = 'yyyy-mm-dd'
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'Sheet1')
    const data = new Uint8Array(
      XLSX.write(wb, { type: 'array', bookType: 'xlsx' })
    )

    const parser = new ExcelParser()
    parser.parse(data)
    const rows = parser.getSheetRows('Sheet1')

    expect(rows[0]).toEqual(['When'])
    expect(rows[1][0]).toBe('2026-04-26')
  })

  test('throws when asking for a sheet that does not exist', () => {
    const data = buildWorkbook({ Sheet1: [['a']] })
    const parser = new ExcelParser()
    parser.parse(data)

    expect(() => parser.getSheetRows('Missing')).toThrow(
      'Sheet "Missing" does not exist in the workbook.'
    )
  })

  test('throws when getSheetRows is called before parse', () => {
    const parser = new ExcelParser()
    expect(() => parser.getSheetRows('Sheet1')).toThrow(
      'Workbook has not been parsed yet.'
    )
  })

  test('accepts a raw ArrayBuffer as well as a Uint8Array', () => {
    const data = buildWorkbook({ Sheet1: [['hello']] })
    const buffer = data.buffer.slice(
      data.byteOffset,
      data.byteOffset + data.byteLength
    )

    const parser = new ExcelParser()
    expect(parser.parse(buffer)).toEqual(['Sheet1'])
    expect(parser.getSheetRows('Sheet1')).toEqual([['hello']])
  })
})

describe('stringifyCell', () => {
  test('returns empty string for null and undefined', () => {
    expect(stringifyCell(null)).toBe('')
    expect(stringifyCell(undefined)).toBe('')
  })

  test('passes strings through untouched', () => {
    expect(stringifyCell('hello')).toBe('hello')
    expect(stringifyCell('')).toBe('')
  })

  test('serialises Date instances as ISO strings', () => {
    const date = new Date(Date.UTC(2026, 3, 26, 12, 0, 0))
    expect(stringifyCell(date)).toBe('2026-04-26T12:00:00.000Z')
  })

  test('coerces numbers and booleans to strings', () => {
    expect(stringifyCell(42)).toBe('42')
    expect(stringifyCell(0)).toBe('0')
    expect(stringifyCell(true)).toBe('true')
    expect(stringifyCell(false)).toBe('false')
  })
})
