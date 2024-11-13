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

export const formulaArrayFilterMixin = {
  getSubType(field) {
    return this.app.$registry.get('formula_type', field.array_formula_type)
  },

  getHasEmptyValueFilterFunction(field) {
    const subType = this.getSubType(field)
    return subType.getHasEmptyValueFilterFunction(field)
  },

  getHasValueLengthIsLowerThanFilterFunction(field) {
    const subType = this.getSubType(field)
    return subType.getHasValueLengthIsLowerThanFilterFunction(field)
  },

  getHasValueContainsFilterFunction(field) {
    const subType = this.getSubType(field)
    return subType.getHasValueContainsFilterFunction(field)
  },

  getHasValueContainsWordFilterFunction(field) {
    const subType = this.getSubType(field)
    return subType.getHasValueContainsWordFilterFunction(field)
  },

  hasValueContainsWordFilter(cellValue, filterValue, field) {
    const subType = this.getSubType(field)
    return subType.hasValueContainsWordFilter(cellValue, filterValue, field)
  },

  hasNotValueContainsWordFilter(cellValue, filterValue, field) {
    const subType = this.getSubType(field)
    return subType.hasNotValueContainsWordFilter(cellValue, filterValue, field)
  },

  getHasValueEqualFilterFunction(field) {
    const subType = this.getSubType(field)
    return subType.getHasValueEqualFilterFunction(field)
  },

  hasValueEqualFilter(cellValue, filterValue, field) {
    const subType = this.getSubType(field)
    return subType.hasValueEqualFilter(cellValue, filterValue, field)
  },

  hasNotValueEqualFilter(cellValue, filterValue, field) {
    const subType = this.getSubType(field)
    return subType.hasNotValueEqualFilter(cellValue, filterValue, field)
  },

  getHasAllValuesEqualFilterFunction(field) {
    return this.getSubType(field)?.getHasAllValuesEqualFilterFunction(field)
  },
}

export const hasSelectOptionIdEqualMixin = Object.assign(
  {},
  hasValueEqualFilterMixin,
  {
    getHasValueEqualFilterFunction(field) {
      const mapOptionIdsToValues = (cellVal) =>
        cellVal.map((v) => ({
          id: v.id,
          value: String(v.value?.id || ''),
        }))
      const hasValueEqualFilter = (cellVal, fltValue) =>
        genericHasValueEqualFilter(mapOptionIdsToValues(cellVal), fltValue)

      return (cellValue, filterValue) => {
        const filterValues = filterValue.trim().split(',')
        return filterValues.reduce((acc, fltValue) => {
          return acc || hasValueEqualFilter(cellValue, String(fltValue))
        }, false)
      }
    },
  }
)

export const hasSelectOptionValueContainsFilterMixin = Object.assign(
  {},
  hasValueContainsFilterMixin,
  {
    getHasValueContainsFilterFunction(field) {
      return (cellValue, filterValue) =>
        genericHasValueContainsFilter(
          cellValue.map((v) => ({ id: v.id, value: v.value?.value || '' })),
          filterValue
        )
    },
  }
)

export const hasSelectOptionValueContainsWordFilterMixin = Object.assign(
  {},
  hasValueContainsWordFilterMixin,
  {
    getHasValueContainsWordFilterFunction(field) {
      return (cellValue, filterValue) =>
        genericHasValueContainsWordFilter(
          cellValue.map((v) => ({ id: v.id, value: v.value?.value || '' })),
          filterValue
        )
    },
  }
)
