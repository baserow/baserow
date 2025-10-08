/**
 * A mixin that can be used to copy and paste row values.
 */

import {
  getRichClipboard,
  setRichClipboard,
  LOCAL_STORAGE_CLIPBOARD_KEY,
} from '@baserow/modules/database/utils/clipboard'

const PAPA_CONFIG = {
  delimiter: '\t',
}

export default {
  methods: {
    /**
     * Prepares the values of the given fields and rows for copying to the clipboard. It
     * returns both a text representation and a json representation of the data. The
     * text representation is a 2D array of strings, where each inner array represents a
     * row and each string represents a cell. The json representation is a 2D array of
     * values, where each inner array represents a row and each value represents a cell.
     * The json representation can contain rich values, such as objects or arrays, that
     * can be later used to paste rich data back into the grid.
     *
     * @param {Array} fields The fields to copy.
     * @param {Array} rows The rows to copy.
     * @param {boolean} includeHeader Whether to include the field names as the first
     */
    prepareValuesForCopy(fields, rows, includeHeader = false) {
      const textData = []
      const jsonData = []
      if (includeHeader) {
        textData.push(fields.map((field) => field.name))
        jsonData.push(fields.map((field) => field.name))
      }
      for (const row of rows) {
        const text = fields.map((field) =>
          this.$registry
            .get('field', field.type)
            .prepareValueForCopy(field, row['field_' + field.id])
        )
        const json = fields.map((field) =>
          this.$registry
            .get('field', field.type)
            .prepareRichValueForCopy(field, row['field_' + field.id])
        )
        textData.push(text)
        jsonData.push(json)
      }
      return { textData, jsonData }
    },
    /**
     * Prepares the given text data as an HTML table. If the text data only contains
     * a single cell, no HTML table is returned as it would conflict with tiptap.
     * The html data is used when pasting into external applications that support rich
     * clipboard data, such as Google Sheets or Excel. If the firstRowIsHeader is true,
     * the first row will be wrapped in <th> tags instead of <td> tags.
     *
     * @param {Array} textData The text data to prepare.
     * @param {boolean} firstRowIsHeader Whether the first row should be treated as a
     * header row.
     * @returns {string|null} The HTML table or null if no table is needed.
     */
    prepareHTMLData(textData, firstRowIsHeader) {
      const table = document.createElement('table')
      const tbody = document.createElement('tbody')

      // For single cells we don't need html clipboard data as it's
      // conflicting with tiptap
      if (textData.length === 1 && textData[0].length === 1) {
        return
      }

      textData.forEach((row, index) => {
        const tr = document.createElement('tr')
        row.forEach((cell) => {
          const td = document.createElement(
            firstRowIsHeader && index === 0 ? 'th' : 'td'
          )
          td.textContent = cell
          tr.appendChild(td)
        })
        tbody.appendChild(tr)
      })
      table.appendChild(tbody)
      return table.outerHTML
    },
    showCopyClipboardError() {
      this.$store.dispatch(
        'toast/error',
        {
          title: this.$t('action.copyToClipboard'),
          message: this.$t('error.copyFailed'),
        },
        { root: true }
      )
    },
    /**
     * Formats the given text and json data for the clipboard and stores the rich
     * representation in local storage. It returns both a tsv representation and an html
     * representation of the text data. The tsv representation is used for plain text
     * clipboard data, the html representation is used when pasting into external
     * applications that support rich clipboard data, such as Google Sheets or Excel.
     * The json representation is stored in local storage to be able to paste rich
     * values back into the Baserow grid later. If the the stored version is the same as
     * the clipboard version, the rich values will be used when pasting instead of the
     * text values, so we can be more accurate (i.e. link row values, select options,
     * etc.)
     *
     * @param {Object} data An object containing the text and json data.
     * @param {Array} data.textData A 2D array of strings representing the text data.
     * @param {Array} data.jsonData A 2D array of values representing the json data.
     * @param {boolean} includeHeader Whether the copied data includes a header row.
     * @returns {Object} An object containing the tsv and html representation of the
     * text data. The html representation can be null if no html table is needed.
     */
    formatClipboardDataAndStoreRichCopy(
      { textData, jsonData },
      includeHeader = false
    ) {
      const tsvData = this.$papa.unparse(textData, PAPA_CONFIG)
      const htmlData = this.prepareHTMLData(textData, includeHeader)
      try {
        localStorage.setItem(
          LOCAL_STORAGE_CLIPBOARD_KEY,
          JSON.stringify({ text: tsvData, json: jsonData })
        )
      } catch (e) {
        this.showCopyClipboardError()
        throw e
      }
      return { tsvData, htmlData }
    },
    /**
     * Copies the given selection to the clipboard. The selection is a promise that
     * resolves to an array containing the fields and rows to copy. The fields are
     * used to determine which columns to copy and in which order. The rows are the
     * actual data to copy. If includeHeader is true, the field names are included as
     * the first row of the copied data.
     *
     * @param {Promise} selectionPromise A promise that resolves to an array containing
     * the fields and rows to copy.
     * @param {boolean} includeHeader Whether to include the field names as the first
     * row of the copied data.
     */
    copySelectionToClipboard(selectionPromise, includeHeader = false) {
      this.$store.dispatch('toast/setCopying', true)
      const dataPromise = selectionPromise
        .then(([fields, rows]) => {
          const { textData, jsonData } = this.prepareValuesForCopy(
            fields,
            rows,
            includeHeader
          )
          this.$store.dispatch('toast/setCopying', false)
          return this.formatClipboardDataAndStoreRichCopy(
            { textData, jsonData },
            includeHeader
          )
        })
        .catch((error) => {
          this.$store.dispatch('toast/setCopying', false)
          throw error
        })

      try {
        this.writeToClipboard(dataPromise)
      } catch (e) {
        if (!document.hasFocus()) {
          window.addEventListener(
            'focus',
            () => this.writeToClipboard(dataPromise),
            { once: true }
          )
        } else {
          this.showCopyClipboardError()
        }
      }
    },
    /**
     * Writes the given data to the clipboard. It tries to write both a plain text
     * representation and a html representation of the data if supported by the browser.
     * If the ClipboardItem API is not supported, it falls back to writing only the
     * plain text representation. If that is also not supported, it falls back to using
     * the rich clipboard utils that uses an older approach to write both a plain text
     * and html representation of the data.
     *
     * @param {Promise} dataPromise A promise that resolves to an object containing
     * the tsv and html representation of the data.
     */
    writeToClipboard(dataPromise) {
      if (typeof ClipboardItem !== 'undefined') {
        const clipboardItem = new ClipboardItem({
          'text/plain': Promise.resolve(dataPromise).then(({ tsvData }) =>
            tsvData ? new Blob([tsvData], { type: 'text/plain' }) : null
          ),
          'text/html': Promise.resolve(dataPromise).then(({ htmlData }) =>
            htmlData ? new Blob([htmlData], { type: 'text/html' }) : null
          ),
        })
        navigator.clipboard.write([clipboardItem])
      } else if (typeof navigator.clipboard?.writeText !== 'undefined') {
        navigator.clipboard.writeText(
          Promise.resolve(dataPromise).then(({ tsvData }) => tsvData)
        )
      } else {
        const richClipboardConfig = {
          'text/plain': Promise.resolve(dataPromise).then(
            ({ tsvData }) => tsvData || null
          ),
          'text/html': Promise.resolve(dataPromise).then(
            ({ htmlData }) => htmlData || null
          ),
        }
        setRichClipboard(richClipboardConfig)
      }
    },
    /**
     * Extracts the clipboard data from the given paste event. It tries to extract
     * both a plain text representation and a json representation of the data. The
     * plain text representation is a 2D array of strings, where each inner array
     * represents a row and each string represents a cell. The json representation
     * is a 2D array of values, where each inner array represents a row and each
     * value represents a cell. The json representation can contain rich values,
     * such as objects or arrays, that can be later used to paste rich data back
     * into the grid, if the versions match.
     *
     * @param {Event} event The paste event.
     * @returns {Array} An array containing the text and json data.
     */
    async extractClipboardData(event) {
      const { textRawData, jsonRawData } = await getRichClipboard(event)
      const { data: textData } = await this.$papa.parsePromise(
        textRawData,
        PAPA_CONFIG
      )

      let jsonData = null
      if (jsonRawData != null) {
        // Check if we have an array of arrays with At least one row with at least
        // one row with a value Otherwise the paste is empty
        if (
          Array.isArray(jsonRawData) &&
          jsonRawData.length === textData.length &&
          jsonRawData.every((row) => Array.isArray(row)) &&
          jsonRawData.some((row) => row.length > 0)
        ) {
          jsonData = jsonRawData
        }
      }

      return [textData, jsonData]
    },
  },
}
