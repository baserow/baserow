import * as XLSX from 'xlsx'

/**
 * Wraps SheetJS to parse spreadsheet files (.xlsx, .xls, .ods) and convert a
 * sheet into a 2D array of strings ready to be fed to the rest of the import
 * pipeline. Cell values are read as formatted text so that dates, numbers and
 * booleans are imported the way the user sees them in their spreadsheet.
 */
export class ExcelParser {
  constructor() {
    this.workbook = null
    this.sheetNames = []
  }

  /**
   * Parses the given ArrayBuffer / Uint8Array as a workbook. Returns the list
   * of sheet names found in the workbook.
   */
  parse(rawData) {
    const data =
      rawData instanceof Uint8Array ? rawData : new Uint8Array(rawData)
    this.workbook = XLSX.read(data, {
      type: 'array',
      cellDates: true,
      cellFormula: false,
    })
    this.sheetNames = this.workbook.SheetNames || []
    return this.sheetNames
  }

  /**
   * Returns the rows of the requested sheet as a 2D array of strings. Empty
   * rows are skipped and trailing empty cells are kept as empty strings so
   * every row has the same length as the widest row in the sheet.
   */
  getSheetRows(sheetName) {
    if (this.workbook === null) {
      throw new Error('Workbook has not been parsed yet.')
    }
    const sheet = this.workbook.Sheets[sheetName]
    if (sheet === undefined) {
      throw new Error(`Sheet "${sheetName}" does not exist in the workbook.`)
    }
    const rows = XLSX.utils.sheet_to_json(sheet, {
      header: 1,
      defval: '',
      blankrows: false,
      raw: false,
    })
    return rows.map((row) => row.map(stringifyCell))
  }
}

/**
 * Convert a cell value coming from SheetJS to a plain string. With `raw: false`
 * SheetJS already returns formatted text for most cell types, but Date objects
 * and `null`/`undefined` still need to be handled here.
 */
export function stringifyCell(value) {
  if (value === null || value === undefined) {
    return ''
  }
  if (value instanceof Date) {
    return value.toISOString()
  }
  if (typeof value === 'string') {
    return value
  }
  return String(value)
}
