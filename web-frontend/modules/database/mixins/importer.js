/**
 * Mixin that introduces helper methods for the importer form component.
 */
import {
  RESERVED_BASEROW_FIELD_NAMES,
  MAX_FIELD_NAME_LENGTH,
} from '@baserow/modules/database/utils/constants'

const IMPORT_PREVIEW_MAX_ROW_COUNT = 6

export default {
  props: {
    mapping: {
      type: Object,
      required: false,
      default: () => {
        return {}
      },
    },
  },

  data() {
    return {
      fileLoadingProgress: 0,
      state: null,
      error: '',
      values: {},
    }
  },
  computed: {
    stateTitle() {
      return this.$t(`importer.${this.state}`)
    },
  },
  methods: {
    resetImporterState() {
      this.state = null
      this.error = ''
      this.values = {}

      this.$emit('getData', null)
      this.$emit('data', { header: [], previewData: [] })
    },
    handleImporterError(error) {
      this.resetImporterState()
      this.fileLoadingProgress = 0
      this.error = error
    },
    /**
     * Adds a header of Field 1, Field 2, etc. if the header is empty,
     * otherwise checks that the existing header has valid and non duplicate field
     * names. If there are invalid or duplicate field names they will be replaced with
     * valid unique field names instead.
     *
     * @param header An array starting of the column name.
     * @param data An array starting with a header row if firstRowHeader is true,
     *    followed by rows of data.
     * @return {*} An updated data object with the first row being a valid unique
     *    header row.
     */
    prepareHeader(header = [], data) {
      const columnCount = Math.max.apply(
        null,
        data.map((entry) => entry.length)
      )

      // If the first row is not the header, a header containing columns named
      // 'Field N' needs to be generated.
      if (!header || header.length === 0) {
        const newHead = []
        for (let i = 1; i <= columnCount; i++) {
          newHead.push(this.$t(`importer.fieldDefaultName`, { count: i }))
        }
        return newHead
      } else {
        // The header row might not be long enough to cover all columns, ensure it does
        // first.
        const newHead = header.map((value) => `${value}`)
        for (let i = newHead.length; i < columnCount; i++) {
          newHead.push(this.$t(`importer.fieldDefaultName`, { count: i }))
        }
        return this.makeHeaderUniqueAndValid(newHead)
      }
    },
    /**
     * Fills the row with a minimum amount of empty columns.
     */
    fill(row, maxLength) {
      for (let i = row.length; i < maxLength; i++) {
        row.push('')
      }
      return row
    },
    /**
     * Generates an object that can used to render a quick preview of the provided
     * data.
     */
    getPreview(head, data) {
      const rows = data.slice(0, IMPORT_PREVIEW_MAX_ROW_COUNT)
      const columns = Math.max.apply(
        null,
        data.map((entry) => entry.length)
      )

      rows.map((row) => this.fill(row, columns))

      return rows
    },
    /**
     * Find the next un-unused column not present or used yet in the nextFreeIndexMap.
     * Will append a number to the returned columnName if it is taken, where that
     * number ensures the returned name is unique. Will respect the maximum allowed
     * field name length. Finally this function will update
     * the nextFreeIndexMap so future calls will not use any columns returned by
     * this function.
     * @param originalColumnName The column name to find the next free unique value for.
     * @param nextFreeIndexMap A map of column name to next free starting index.
     * @param startingIndex The starting index to start from if no index is found in
     *    the map.
     * @return {string} A column name possibly postfixed with a number to ensure it
     *    is unique.
     */
    findNextFreeName(originalColumnName, nextFreeIndexMap, startingIndex) {
      let i = nextFreeIndexMap.get(originalColumnName) || startingIndex
      while (true) {
        const suffixToAppend = ` ${i}`
        let nextColumnNameToCheck

        // If appending a number to the columnName in order to make it
        // unique will return a string that is longer than the maximum
        // allowed field name length, we need to further slice the
        // columnName as to not go above the maximum allowed length.
        if (
          originalColumnName.length + suffixToAppend.length >
          MAX_FIELD_NAME_LENGTH
        ) {
          nextColumnNameToCheck = `${originalColumnName.slice(
            0,
            -suffixToAppend.length
          )}${suffixToAppend}`
        } else {
          nextColumnNameToCheck = `${originalColumnName}${suffixToAppend}`
        }
        if (!nextFreeIndexMap.has(nextColumnNameToCheck)) {
          nextFreeIndexMap.set(originalColumnName, i + 1)
          return nextColumnNameToCheck
        }
        i++
      }
    },
    /**
     * Given a column name this function will return a new name which is guaranteed
     * to be unique and valid. If the originally provided name is unique and valid
     * then it will be returned untouched.
     *
     * @param column The column name to check.
     * @param nextFreeIndexMap A map of column names to an index number. A value of 0
     *    indicates that the key is a column name which exists in the table but has not
     *    yet been returned yet. A number higher than 0 indicates that the column has
     *    already occurred and the index needs to be appended to the name to generate a
     *    new unique column name.
     * @return {string|*} A valid unique column name.
     */
    makeColumnNameUniqueAndValidIfNotAlready(column, nextFreeIndexMap) {
      if (column === '') {
        return this.findNextFreeName('Field', nextFreeIndexMap, 1)
      } else if (RESERVED_BASEROW_FIELD_NAMES.includes(column)) {
        return this.findNextFreeName(column, nextFreeIndexMap, 2)
      } else if (nextFreeIndexMap.get(column) > 0) {
        return this.findNextFreeName(column, nextFreeIndexMap, 2)
      } else {
        nextFreeIndexMap.set(column, 2)
        return column
      }
    },
    /**
     * Ensures that the uploaded field names are unique, non blank, don't exceed
     * the maximum field name length and don't use any reserved Baserow field names.
     * @param {*[]} head An array of field names to be checked.
     * @return A new array of field names which are guaranteed to be unique and valid.
     */
    makeHeaderUniqueAndValid(head) {
      const nextFreeIndexMap = new Map()
      for (let i = 0; i < head.length; i++) {
        const truncatedColumn = head[i].trim().slice(0, MAX_FIELD_NAME_LENGTH)
        nextFreeIndexMap.set(truncatedColumn, 0)
      }
      const uniqueAndValidHeader = []
      for (let i = 0; i < head.length; i++) {
        const column = head[i]
        const trimmedColumn = column.trim()
        const truncatedColumn = trimmedColumn.slice(0, MAX_FIELD_NAME_LENGTH)
        const uniqueValidName = this.makeColumnNameUniqueAndValidIfNotAlready(
          truncatedColumn,
          nextFreeIndexMap
        )
        uniqueAndValidHeader.push(uniqueValidName)
      }
      return uniqueAndValidHeader
    },
  },
}
