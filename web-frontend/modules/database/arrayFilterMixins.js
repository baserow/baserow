import {
  genericHasValueEqualFilter,
  genericHasValueContainsFilter,
  genericHasValueContainsWordFilter,
  genericHasEmptyValueFilter,
  genericHasValueLengthLowerThanFilter,
  genericHasAllValuesEqualFilter,
} from '@baserow/modules/database/utils/fieldFilters'

export const hasEmptyValueFilterMixin = {
  getHasEmptyValueFilterFunction(field) {
    return genericHasEmptyValueFilter
  },
}

export const hasAllValuesEqualFilterMixin = {
  getHasAllValuesEqualFilterFunction(field) {
    return genericHasAllValuesEqualFilter
  },

  hasAllValuesEqualFilter(cellValue, filterValue, field) {
    return (
      filterValue === '' ||
      this.getHasAllValuesEqualFilterFunction(field)(cellValue, filterValue)
    )
  },
  hasNotAllValuesEqualFilter(cellValue, filterValue, field) {
    return (
      filterValue === '' ||
      !this.getHasAllValuesEqualFilterFunction(field)(cellValue, filterValue)
    )
  },
}
export const hasValueEqualFilterMixin = {
  getHasValueEqualFilterFunction(field) {
    return genericHasValueEqualFilter
  },
  hasValueEqualFilter(cellValue, filterValue, field) {
    return (
      filterValue === '' ||
      this.getHasValueEqualFilterFunction(field)(cellValue, filterValue)
    )
  },
  hasNotValueEqualFilter(cellValue, filterValue, field) {
    return (
      filterValue === '' ||
      !this.getHasValueEqualFilterFunction(field)(cellValue, filterValue)
    )
  },
}

export const hasValueContainsFilterMixin = {
  getHasValueContainsFilterFunction(field) {
    return genericHasValueContainsFilter
  },
  hasValueContainsFilter(cellValue, filterValue, field) {
    return (
      filterValue === '' ||
      this.getHasValueContainsFilterFunction(field)(cellValue, filterValue)
    )
  },
  hasNotValueContainsFilter(cellValue, filterValue, field) {
    return (
      filterValue === '' ||
      !this.getHasValueContainsFilterFunction(field)(cellValue, filterValue)
    )
  },
}

export const hasValueContainsWordFilterMixin = {
  getHasValueContainsWordFilterFunction(field) {
    return genericHasValueContainsWordFilter
  },
  hasValueContainsWordFilter(cellValue, filterValue, field) {
    return (
      filterValue === '' ||
      this.getHasValueContainsWordFilterFunction(field)(cellValue, filterValue)
    )
  },
  hasNotValueContainsWordFilter(cellValue, filterValue, field) {
    return (
      filterValue === '' ||
      !this.getHasValueContainsWordFilterFunction(field)(cellValue, filterValue)
    )
  },
}

export const hasValueLengthIsLowerThanFilterMixin = {
  getHasValueLengthIsLowerThanFilterFunction(field) {
    return genericHasValueLengthLowerThanFilter
  },
}
