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
  test('parses a single-sheet workbook into rows of strings', async () => {
    const data = buildWorkbook({
      Sheet1: [
        ['Name', 'Age', 'Active'],
        ['Alice', 30, true],
        ['Bob', 25, false],
      ],
    })
    const parser = new ExcelParser()
    const sheets = await parser.parse(data)

    expect(sheets).toEqual(['Sheet1'])
    expect(parser.getSheetRows('Sheet1')).toEqual([
      ['Name', 'Age', 'Active'],
      ['Alice', '30', 'TRUE'],
      ['Bob', '25', 'FALSE'],
    ])
  })

  test('exposes every sheet name in workbook order', async () => {
    const data = buildWorkbook({
      Customers: [['Name'], ['Alice']],
      Orders: [['Id'], ['1']],
    })
    const parser = new ExcelParser()

    expect(await parser.parse(data)).toEqual(['Customers', 'Orders'])
    expect(parser.getSheetRows('Customers')).toEqual([['Name'], ['Alice']])
    expect(parser.getSheetRows('Orders')).toEqual([['Id'], ['1']])
  })

  test('skips fully empty rows but keeps trailing empty cells', async () => {
    const data = buildWorkbook({
      Sheet1: [['a', 'b', 'c'], [], ['x', '', 'z']],
    })
    const parser = new ExcelParser()
    await parser.parse(data)

    expect(parser.getSheetRows('Sheet1')).toEqual([
      ['a', 'b', 'c'],
      ['x', '', 'z'],
    ])
  })

  test('formats date cells using their cell format', async () => {
    const ws = XLSX.utils.aoa_to_sheet([
      ['When'],
      [new Date(Date.UTC(2026, 3, 26))],
    ])
    ws.A2.z = 'yyyy-mm-dd'
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'Sheet1')
    const data = new Uint8Array(
      XLSX.write(wb, { type: 'array', bookType: 'xlsx' })
    )

    const parser = new ExcelParser()
    await parser.parse(data)
    const rows = parser.getSheetRows('Sheet1')

    expect(rows[0]).toEqual(['When'])
    expect(rows[1][0]).toBe('2026-04-26')
  })

  test('renders unformatted date cells via the dateNF fallback', async () => {
    // The xlsx write path auto-assigns `m/d/yy` to date cells, so to actually
    // exercise the dateNF fallback we strip `z` from the cached workbook
    // after parse(). Without dateNF the cell would come back as a Date object
    // (or a locale-dependent string) instead of formatted text.
    const ws = XLSX.utils.aoa_to_sheet([
      ['When'],
      [new Date(Date.UTC(2026, 3, 26, 12, 30, 45))],
    ])
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'Sheet1')
    const data = new Uint8Array(
      XLSX.write(wb, { type: 'array', bookType: 'xlsx' })
    )

    const parser = new ExcelParser()
    await parser.parse(data)
    // Clear both the format (`z`) and the cached formatted text (`w`) so
    // SheetJS has to fall back to `dateNF` when rendering the cell.
    delete parser.workbook.Sheets.Sheet1.A2.z
    delete parser.workbook.Sheets.Sheet1.A2.w
    const rows = parser.getSheetRows('Sheet1')

    expect(typeof rows[1][0]).toBe('string')
    expect(rows[1][0]).toBe('2026-04-26 12:30:45')
  })

  test('previewRows truncates parsed rows but preserves the full row count', async () => {
    const rows = [['header']]
    for (let i = 0; i < 100; i++) {
      rows.push(['row ' + i])
    }
    const data = buildWorkbook({ Sheet1: rows })
    const parser = new ExcelParser()
    await parser.parse(data, { previewRows: 5 })

    // Only the first 5 rows should be available via getSheetRows...
    const previewed = parser.getSheetRows('Sheet1')
    expect(previewed).toEqual([
      ['header'],
      ['row 0'],
      ['row 1'],
      ['row 2'],
      ['row 3'],
    ])

    // ...but the parser must still report the full original sheet size so
    // the importer can run its row-count limit check before submission.
    expect(parser.getTotalRowCount('Sheet1')).toBe(101)
  })

  test('getTotalRowCount works after a full (non-preview) parse', async () => {
    const data = buildWorkbook({
      Sheet1: [['a'], ['b'], ['c'], ['d']],
    })
    const parser = new ExcelParser()
    await parser.parse(data)

    expect(parser.getTotalRowCount('Sheet1')).toBe(4)
  })

  test('getTotalRowCount throws before parse and for unknown sheets', async () => {
    const parser = new ExcelParser()
    expect(() => parser.getTotalRowCount('Sheet1')).toThrow(
      'Workbook has not been parsed yet.'
    )

    const data = buildWorkbook({ Sheet1: [['a']] })
    await parser.parse(data)
    expect(() => parser.getTotalRowCount('Missing')).toThrow(
      'Sheet "Missing" does not exist in the workbook.'
    )
  })

  test('throws when asking for a sheet that does not exist', async () => {
    const data = buildWorkbook({ Sheet1: [['a']] })
    const parser = new ExcelParser()
    await parser.parse(data)

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

  test('accepts a raw ArrayBuffer as well as a Uint8Array', async () => {
    const data = buildWorkbook({ Sheet1: [['hello']] })
    const buffer = data.buffer.slice(
      data.byteOffset,
      data.byteOffset + data.byteLength
    )

    const parser = new ExcelParser()
    expect(await parser.parse(buffer)).toEqual(['Sheet1'])
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

  test('coerces numbers and booleans to strings', () => {
    expect(stringifyCell(42)).toBe('42')
    expect(stringifyCell(0)).toBe('0')
    expect(stringifyCell(true)).toBe('true')
    expect(stringifyCell(false)).toBe('false')
  })
})
