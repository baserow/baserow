let xlsxPromise = null
function loadXLSX() {
  if (xlsxPromise === null) {
    xlsxPromise = import('xlsx')
  }
  return xlsxPromise
}

/**
 * Wraps SheetJS to parse spreadsheet files (.xlsx, .xls, .ods) and convert a
 * sheet into a 2D array of strings ready to be fed to the rest of the import
 * pipeline. Cell values are read as formatted text so that dates, numbers and
 * booleans are imported the way the user sees them in their spreadsheet.
 *
 */
export class ExcelParser {
  constructor() {
    this.workbook = null
    this.sheetNames = []
    this.xlsx = null
  }

  /**
   * Parses the given ArrayBuffer / Uint8Array as a workbook. Returns the list
   * of sheet names found in the workbook.
   *
   * When `previewRows` is set, SheetJS only parses the first N rows of every
   * sheet. The original sheet range is preserved on `sheet['!fullref']` so
   * `getTotalRowCount()` can still report how big each sheet really is. This
   * keeps the initial preview fast even for large workbooks; the full parse
   * happens later via a separate `ExcelParser` instance during import.
   */
  async parse(rawData, { previewRows = null } = {}) {
    const data =
      rawData instanceof Uint8Array ? rawData : new Uint8Array(rawData)
    this.xlsx = await loadXLSX()
    const opts = {
      type: 'array',
      cellDates: true,
      cellFormula: false,
    }
    if (previewRows !== null && previewRows > 0) {
      opts.sheetRows = previewRows
    }
    this.workbook = this.xlsx.read(data, opts)
    this.sheetNames = this.workbook.SheetNames || []
    return this.sheetNames
  }

  /**
   * Returns the total number of rows in the requested sheet, including any
   * trailing empty rows in the sheet's range. Safe to call after a partial
   * (`previewRows`) parse: SheetJS preserves the original range on
   * `!fullref`, so we report the full sheet size rather than the truncated
   * preview window.
   */
  getTotalRowCount(sheetName) {
    if (this.workbook === null) {
      throw new Error('Workbook has not been parsed yet.')
    }
    const sheet = this.workbook.Sheets[sheetName]
    if (sheet === undefined) {
      throw new Error(`Sheet "${sheetName}" does not exist in the workbook.`)
    }
    const range = sheet['!fullref'] || sheet['!ref']
    if (!range) {
      return 0
    }
    const decoded = this.xlsx.utils.decode_range(range)
    return decoded.e.r - decoded.s.r + 1
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
    const rows = this.xlsx.utils.sheet_to_json(sheet, {
      header: 1,
      defval: '',
      blankrows: false,
      raw: false,
      // Fallback format used by SheetJS when a date cell has no explicit
      // number format. Cells that *do* carry a format (`z`) still render with
      // their own format, matching what the user sees in their spreadsheet.
      dateNF: 'yyyy-mm-dd hh:mm:ss',
    })
    return rows.map((row) => row.map(stringifyCell))
  }
}

/**
 * Convert a cell value coming from SheetJS to a plain string. With `raw: false`
 * (and `dateNF` for date cells without a format) SheetJS already returns
 * formatted text for every cell type — only `null`/`undefined` still need
 * handling here.
 */
export function stringifyCell(value) {
  if (value === null || value === undefined) {
    return ''
  }
  return typeof value === 'string' ? value : String(value)
}
