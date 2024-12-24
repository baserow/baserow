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

    if (value === '' || value === null) {
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

export function genericHasValueContainsFilter(cellValue, filterValue) {
  if (!Array.isArray(cellValue)) {
    return false
  }

  filterValue = String(filterValue).toLowerCase().trim()

  for (let i = 0; i < cellValue.length; i++) {
    const value = String(cellValue[i].value).toLowerCase().trim()

    if (value.includes(filterValue)) {
      return true
    }
  }

  return false
}

export function genericHasValueContainsWordFilter(cellValue, filterValue) {
  if (!Array.isArray(cellValue)) {
    return false
  }

  filterValue = String(filterValue).toLowerCase().trim()
  filterValue = filterValue.replace(/[-[\]{}()*+?.,\\^$|#]/g, '\\$&')

  for (let i = 0; i < cellValue.length; i++) {
    if (cellValue[i].value == null) {
      continue
    }
    const value = String(cellValue[i].value).toLowerCase().trim()
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

function doArrayNumberComparison(cellValue, filterValue, compareFunc) {
  const filterNr = new BigNumber(filterValue)
  if (!Array.isArray(cellValue) || filterNr.isNaN()) {
    return false
  }
  return _.some(_.map(cellValue, 'value'), (item) =>
    compareFunc(new BigNumber(item), filterNr)
  )
}

export function numericHasValueHigherThanFilterFunction(
  cellValue,
  filterValue
) {
  return doArrayNumberComparison(
    cellValue,
    filterValue,
    (arrayItemNr, filterNr) => arrayItemNr.isGreaterThan(filterNr)
  )
}

export function numericHasValueHigherThanOrEqualFilterFunction(
  cellValue,
  filterValue
) {
  return doArrayNumberComparison(
    cellValue,
    filterValue,
    (arrayItemNr, filterNr) => arrayItemNr.isGreaterThanOrEqualTo(filterNr)
  )
}

export function numericHasValueLowerThanFilterFunction(cellValue, filterValue) {
  return doArrayNumberComparison(
    cellValue,
    filterValue,
    (arrayItemNr, filterNr) => arrayItemNr.isLessThan(filterNr)
  )
}

export function numericHasValueLowerThanOrEqualFilterFunction(
  cellValue,
  filterValue
) {
  return doArrayNumberComparison(
    cellValue,
    filterValue,
    (arrayItemNr, filterNr) => arrayItemNr.isLessThanOrEqualTo(filterNr)
  )
}

export function numericHasValueEqualToFilterFunction(cellValue, filterValue) {
  return doArrayNumberComparison(
    cellValue,
    filterValue,
    (arrayItemNr, filterNr) => arrayItemNr.isEqualTo(filterNr)
  )
}
