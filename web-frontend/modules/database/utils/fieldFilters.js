// We can't use the humanReadable value here as:
// A: it contains commas which we don't want to match against
// B: even if we removed the commas and compared filterValue against the concatted
//    list of file names, we don't want the filterValue to accidentally match the end
//    of one filename and the start of another.
import _ from 'lodash'
import BigNumber from 'bignumber.js'

export function filenameContainsFilter(
  rowValue,
  humanReadableRowValue,
  filterValue
) {
  filterValue = filterValue.toString().toLowerCase().trim()

  for (let i = 0; i < rowValue.length; i++) {
    const visibleName = rowValue[i].visible_name.toString().toLowerCase().trim()

    if (visibleName.includes(filterValue)) {
      return true
    }
  }

  return false
}

export function genericContainsFilter(
  rowValue,
  humanReadableRowValue,
  filterValue
) {
  if (humanReadableRowValue == null) {
    return false
  }
  humanReadableRowValue = String(humanReadableRowValue).toLowerCase().trim()
  filterValue = String(filterValue).toLowerCase().trim()

  return humanReadableRowValue.includes(filterValue)
}

export function genericContainsWordFilter(
  rowValue,
  humanReadableRowValue,
  filterValue
) {
  if (humanReadableRowValue == null) {
    return false
  }
  humanReadableRowValue = String(humanReadableRowValue).toLowerCase().trim()
  filterValue = String(filterValue).toLowerCase().trim()
  // check using regex to match whole words
  // make sure to escape the filterValue as it may contain regex special characters
  filterValue = filterValue.replace(/[-[\]{}()*+?.,\\^$|#]/g, '\\$&')
  return !!humanReadableRowValue.match(new RegExp(`\\b${filterValue}\\b`))
}

export function genericHasEmptyValueFilter(cellValue, filterValue) {
  if (!Array.isArray(cellValue)) {
    return false
  }

  for (let i = 0; i < cellValue.length; i++) {
    const value = cellValue[i].value

    if (
      value === '' ||
      value === null ||
      (Array.isArray(value) && value.length === 0)
    ) {
      return true
    }
  }

  return false
}

export function genericHasAllValuesEqualFilter(cellValue, filterValue) {
  if (!Array.isArray(cellValue)) {
    return false
  }

  if (cellValue.length === 0) {
    return false
  }
  return _.every(_.map(cellValue, 'value'), (inVal) => inVal === filterValue)
}

export function genericHasValueEqualFilter(cellValue, filterValue) {
  if (!Array.isArray(cellValue)) {
    return false
  }

  for (let i = 0; i < cellValue.length; i++) {
    const value = cellValue[i].value
    if (value === filterValue) {
      return true
    }
  }

  return false
}

export function genericHasValueContainsFilter(
  cellValue,
  filterValue,
  valueField = 'value'
) {
  if (!Array.isArray(cellValue)) {
    return false
  }

  filterValue = String(filterValue).toLowerCase().trim()

  for (let i = 0; i < cellValue.length; i++) {
    const value = String(cellValue[i][valueField]).toLowerCase().trim()
    if (value.includes(filterValue)) {
      return true
    }
  }

  return false
}

export function genericHasValueContainsWordFilter(
  cellValue,
  filterValue,
  valueField = 'value'
) {
  if (!Array.isArray(cellValue)) {
    return false
  }

  filterValue = String(filterValue).toLowerCase().trim()
  filterValue = filterValue.replace(/[-[\]{}()*+?.,\\^$|#]/g, '\\$&')

  for (let i = 0; i < cellValue.length; i++) {
    if (cellValue[i][valueField] == null) {
      continue
    }
    const value = String(cellValue[i][valueField]).toLowerCase().trim()
    if (value.match(new RegExp(`\\b${filterValue}\\b`))) {
      return true
    }
  }

  return false
}

export function genericHasValueLengthLowerThanFilter(cellValue, filterValue) {
  if (!Array.isArray(cellValue)) {
    return false
  }

  for (let i = 0; i < cellValue.length; i++) {
    if (cellValue[i].value == null) {
      continue
    }
    const valueLength = String(cellValue[i].value).length
    if (valueLength < filterValue) {
      return true
    }
  }

  return false
}

export const ComparisonOperator = {
  EQUAL: '=',
  HIGHER_THAN: '>',
  HIGHER_THAN_OR_EQUAL: '>=',
  LOWER_THAN: '<',
  LOWER_THAN_OR_EQUAL: '<=',
}

function doNumericArrayComparison(cellValue, filterValue, compareFunc) {
  const filterNr = new BigNumber(filterValue)
  if (!Array.isArray(cellValue) || filterNr.isNaN()) {
    return false
  }
  return _.some(_.map(cellValue, 'value'), (item) =>
    compareFunc(new BigNumber(item), filterNr)
  )
}

export function numericHasValueComparableToFilterFunction(comparisonOp) {
  return (cellValue, filterValue) => {
    let compareFunc
    switch (comparisonOp) {
      case ComparisonOperator.EQUAL:
        compareFunc = (a, b) => a.isEqualTo(b)
        break
      case ComparisonOperator.HIGHER_THAN:
        compareFunc = (a, b) => a.isGreaterThan(b)
        break
      case ComparisonOperator.HIGHER_THAN_OR_EQUAL:
        compareFunc = (a, b) => a.isGreaterThanOrEqualTo(b)
        break
      case ComparisonOperator.LOWER_THAN:
        compareFunc = (a, b) => a.isLessThan(b)
        break
      case ComparisonOperator.LOWER_THAN_OR_EQUAL:
        compareFunc = (a, b) => a.isLessThanOrEqualTo(b)
        break
    }
    if (compareFunc === undefined) {
      throw new Error('Invalid comparison operator')
    }

    return doNumericArrayComparison(
      cellValue,
      filterValue,
      (arrayItemNr, filterNr) => compareFunc(arrayItemNr, filterNr)
    )
  }
}
