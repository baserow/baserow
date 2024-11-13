// We can't use the humanReadable value here as:
// A: it contains commas which we don't want to match against
// B: even if we removed the commas and compared filterValue against the concatted
//    list of file names, we don't want the filterValue to accidentally match the end
//    of one filename and the start of another.
import _ from 'lodash'

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
  humanReadableRowValue = humanReadableRowValue.toString().toLowerCase().trim()
  filterValue = filterValue.toString().toLowerCase().trim()

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
  humanReadableRowValue = humanReadableRowValue.toString().toLowerCase().trim()
  filterValue = filterValue.toString().toLowerCase().trim()
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

  filterValue = filterValue.toString().toLowerCase().trim()

  for (let i = 0; i < cellValue.length; i++) {
    const value = cellValue[i].value.toString().toLowerCase().trim()

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

  filterValue = filterValue.toString().toLowerCase().trim()
  filterValue = filterValue.replace(/[-[\]{}()*+?.,\\^$|#]/g, '\\$&')

  for (let i = 0; i < cellValue.length; i++) {
    if (cellValue[i].value == null) {
      continue
    }
    const value = cellValue[i].value.toString().toLowerCase().trim()
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
    const valueLength = cellValue[i].value.toString().length
    if (valueLength < filterValue) {
      return true
    }
  }

  return false
}
