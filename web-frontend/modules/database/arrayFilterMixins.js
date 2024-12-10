import {
  genericHasValueEqualFilter,
  genericHasValueContainsFilter,
  genericHasValueContainsWordFilter,
  genericHasEmptyValueFilter,
  genericHasValueLengthLowerThanFilter,
  genericHasAllValuesEqualFilter,
  genericHasValueHigherThanFilterFunction,
  genericHasValueLowerThanFilterFunction,
  genericHasValueLowerThanOrEqualFilterFunction,
  genericHasValueHigherThanOrEqualFilterFunction,
  genericHasNotValueHigherThanFilterFunction,
  genericHasNotValueLowerThanFilterFunction,
  genericHasNotValueHigherThanOrEqualFilterFunction,
  genericHasNotValueLowerThanOrEqualFilterFunction,
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

export const hasValueHigherOrLowerThanFilterMixin = {
  _wrapChecks(callable) {
    return (cellValue, filterValue) => {
      if (filterValue === null || filterValue === '') {
        return true
      }
      return callable(cellValue, filterValue)
    }
  },

  getHasValueHigherThanFilterFunction(field) {
    return this._wrapChecks(genericHasValueHigherThanFilterFunction)
  },

  getHasValueLowerThanFilterFunction(field) {
    return this._wrapChecks(genericHasValueLowerThanFilterFunction)
  },
  getHasValueHigherThanOrEqualFilterFunction(field) {
    return this._wrapChecks(genericHasValueHigherThanOrEqualFilterFunction)
  },

  getHasValueLowerThanOrEqualFilterFunction(field) {
    return this._wrapChecks(genericHasValueLowerThanOrEqualFilterFunction)
  },

  getHasNotValueHigherThanFilterFunction(field) {
    return this._wrapChecks(genericHasNotValueHigherThanFilterFunction)
  },

  getHasNotValueLowerThanFilterFunction(field) {
    return this._wrapChecks(genericHasNotValueLowerThanFilterFunction)
  },
  getHasNotValueHigherThanOrEqualFilterFunction(field) {
    return this._wrapChecks(genericHasNotValueHigherThanOrEqualFilterFunction)
  },

  getHasNotValueLowerThanOrEqualFilterFunction(field) {
    return this._wrapChecks(genericHasNotValueLowerThanOrEqualFilterFunction)
  },

  hasValueHigherThanFilter(cellValue, filterValue, field) {
    return this.getHasValueHigherThanFilterFunction(field)(
      cellValue,
      filterValue
    )
  },
  hasValueHigherThanOrEqualFilter(cellValue, filterValue, field) {
    return this.getHasValueHigherThanOrEqualFilterFunction(field)(
      cellValue,
      filterValue
    )
  },

  hasValueLowerThanFilter(cellValue, filterValue, field) {
    return this.getHasValueLowerThanFilterFunction(field)(
      cellValue,
      filterValue
    )
  },
  hasValueLowerThanOrEqualFilter(cellValue, filterValue, field) {
    return this.getHasValueLowerThanOrEqualFilterFunction(field)(
      cellValue,
      filterValue
    )
  },

  hasNotValueHigherThanFilter(cellValue, filterValue, field) {
    return this.getHasNotValueHigherThanFilterFunction(field)(
      cellValue,
      filterValue
    )
  },
  hasNotValueHigherThanOrEqualFilter(cellValue, filterValue, field) {
    return this.getHasNotValueHigherThanOrEqualFilterFunction(field)(
      cellValue,
      filterValue
    )
  },

  hasNotValueLowerThanFilter(cellValue, filterValue, field) {
    return this.getHasNotValueLowerThanFilterFunction(field)(
      cellValue,
      filterValue
    )
  },
  hasNotValueLowerThanOrEqualFilter(cellValue, filterValue, field) {
    return this.getHasNotValueLowerThanOrEqualFilterFunction(field)(
      cellValue,
      filterValue
    )
  },
}

export const formulaFieldArrayFilterMixin = {
  hasValueHigherThanFilter(cellValue, filterValue, field) {
    return this.getFormulaSubtype(field)?.hasValueHigherThanFilter(
      cellValue,
      filterValue,
      field
    )
  },
  hasValueHigherThanOrEqualFilter(cellValue, filterValue, field) {
    return this.getFormulaSubtype(field)?.hasValueHigherThanOrEqualFilter(
      cellValue,
      filterValue,
      field
    )
  },

  hasValueLowerThanFilter(cellValue, filterValue, field) {
    return this.getFormulaSubtype(field)?.hasValueLowerThanFilter(
      cellValue,
      filterValue,
      field
    )
  },
  hasValueLowerThanOrEqualFilter(cellValue, filterValue, field) {
    return this.getFormulaSubtype(field)?.hasValueLowerThanOrEqualFilter(
      cellValue,
      filterValue,
      field
    )
  },

  hasNotValueHigherThanFilter(cellValue, filterValue, field) {
    return this.getFormulaSubtype(field)?.hasNotValueHigherThanFilter(
      cellValue,
      filterValue,
      field
    )
  },
  hasNotValueHigherThanOrEqualFilter(cellValue, filterValue, field) {
    return this.getFormulaSubtype(field)?.hasNotValueHigherThanOrEqualFilter(
      cellValue,
      filterValue,
      field
    )
  },

  hasNotValueLowerThanFilter(cellValue, filterValue, field) {
    return this.getFormulaSubtype(field)?.hasNotValueLowerThanFilter(
      cellValue,
      filterValue,
      field
    )
  },
  hasNotValueLowerThanOrEqualFilter(cellValue, filterValue, field) {
    return this.getFormulaSubtype(field)?.hasNotValueLowerThanOrEqualFilter(
      cellValue,
      filterValue,
      field
    )
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
  hasValueHigherThanFilter(cellValue, filterValue, field) {
    return this.getSubType(field)?.hasValueHigherThanFilter(
      cellValue,
      filterValue,
      field
    )
  },
  hasValueHigherThanOrEqualFilter(cellValue, filterValue, field) {
    return this.getSubType(field)?.hasValueHigherThanOrEqualFilter(
      cellValue,
      filterValue,
      field
    )
  },

  hasValueLowerThanFilter(cellValue, filterValue, field) {
    return this.getSubType(field)?.hasValueLowerThanFilter(
      cellValue,
      filterValue,
      field
    )
  },
  hasValueLowerThanOrEqualFilter(cellValue, filterValue, field) {
    return this.getSubType(field)?.hasValueLowerThanOrEqualFilter(
      cellValue,
      filterValue,
      field
    )
  },

  hasNotValueHigherThanFilter(cellValue, filterValue, field) {
    return this.getSubType(field)?.hasNotValueHigherThanFilter(
      cellValue,
      filterValue,
      field
    )
  },
  hasNotValueHigherThanOrEqualFilter(cellValue, filterValue, field) {
    return this.getSubType(field)?.hasNotValueHigherThanOrEqualFilter(
      cellValue,
      filterValue,
      field
    )
  },

  hasNotValueLowerThanFilter(cellValue, filterValue, field) {
    return this.getSubType(field)?.hasNotValueLowerThanFilter(
      cellValue,
      filterValue,
      field
    )
  },
  hasNotValueLowerThanOrEqualFilter(cellValue, filterValue, field) {
    return this.getSubType(field)?.hasNotValueLowerThanOrEqualFilter(
      cellValue,
      filterValue,
      field
    )
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
