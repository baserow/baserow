import {
  genericHasValueEqualFilter,
  genericHasValueContainsFilter,
  genericHasValueContainsWordFilter,
  genericHasEmptyValueFilter,
  genericHasValueLengthLowerThanFilter,
  genericHasAllValuesEqualFilter,
  numericHasValueComparableToFilterFunction,
  ComparisonOperator,
} from '@baserow/modules/database/utils/fieldFilters'
import _ from 'lodash'

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

export const hasNumericValueComparableToFilterMixin = {
  // equal to
  getHasValueEqualFilterFunction(field) {
    return numericHasValueComparableToFilterFunction(ComparisonOperator.EQUAL)
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

  /**
   * All other comparison operators: higher_than, lower_than, etc.
   */
  hasValueComparableToFilter(
    cellValue,
    filterValue,
    field,
    comparisonOperator
  ) {
    return numericHasValueComparableToFilterFunction(comparisonOperator)(
      cellValue,
      filterValue
    )
  },
}

/*
 * Mixin for the FormulaField to handle the array formula filters for number fields.
 */
export const formulaFieldArrayFilterMixin = Object.assign(
  {},
  hasAllValuesEqualFilterMixin,
  hasEmptyValueFilterMixin,
  hasValueEqualFilterMixin,
  hasValueContainsFilterMixin,
  hasValueContainsWordFilterMixin,
  hasValueLengthIsLowerThanFilterMixin,
  {
    getHasAllValuesEqualFilterFunction(field) {
      return this.getFormulaType(field)?.getHasAllValuesEqualFilterFunction(
        field
      )
    },

    getHasEmptyValueFilterFunction(field) {
      return this.getFormulaType(field)?.getHasEmptyValueFilterFunction(field)
    },

    getHasValueEqualFilterFunction(field) {
      return this.getFormulaType(field)?.getHasValueEqualFilterFunction(field)
    },

    getHasValueContainsFilterFunction(field) {
      return this.getFormulaType(field)?.getHasValueContainsFilterFunction(
        field
      )
    },

    getHasValueContainsWordFilterFunction(field) {
      return this.getFormulaType(field)?.getHasValueContainsWordFilterFunction(
        field
      )
    },

    getHasValueLengthIsLowerThanFilterFunction(field) {
      return this.getFormulaType(
        field
      )?.getHasValueLengthIsLowerThanFilterFunction(field)
    },

    hasValueComparableToFilter(
      cellValue,
      filterValue,
      field,
      comparisonOperator
    ) {
      return this.getFormulaType(field)?.hasValueComparableToFilter(
        cellValue,
        filterValue,
        field,
        comparisonOperator
      )
    },
  }
)

/*
 * Mixin for the BaserowFormulaArrayType to proxy all the array filters to the
 * correct sub type.
 */
export const baserowFormulaArrayTypeFilterMixin = {
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

  hasValueComparableToFilter(
    cellValue,
    filterValue,
    field,
    comparisonOperator
  ) {
    return this.getSubType(field)?.hasValueComparableToFilter(
      cellValue,
      filterValue,
      field,
      comparisonOperator
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
          value: String(v.value?.id ?? ''),
        }))
      const hasValueEqualFilter = (cellVal, fltValue) =>
        genericHasValueEqualFilter(mapOptionIdsToValues(cellVal), fltValue)

      return (cellValue, filterValue) => {
        const filterValues = String(filterValue ?? '')
          .trim()
          .split(',')
        return filterValues.some((fltValue) =>
          hasValueEqualFilter(cellValue, String(fltValue))
        )
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

export const hasNestedSelectOptionValueContainsFilterMixin = Object.assign(
  {},
  hasValueContainsFilterMixin,
  {
    _getHasValueContainsFilterFunction(cellValue, filterValue) {
      return cellValue.some((v) =>
        genericHasValueContainsFilter(v?.value || [], filterValue)
      )
    },
    getHasValueContainsFilterFunction(field) {
      return (cellValue, filterValue) => {
        if (!Array.isArray(cellValue) || cellValue.length === 0) {
          return false
        }
        return this._getHasValueContainsFilterFunction(cellValue, filterValue)
      }
    },
  }
)

export const hasNestedSelectOptionValueContainsWordFilterMixin = Object.assign(
  {},
  hasValueContainsWordFilterMixin,
  {
    _getHasValueContainsWordFilterFunction(cellValue, filterValue) {
      return cellValue.some((v) =>
        genericHasValueContainsWordFilter(v?.value || [], filterValue)
      )
    },
    getHasValueContainsWordFilterFunction(field) {
      return (cellValue, filterValue) => {
        if (!Array.isArray(cellValue) || cellValue.length === 0) {
          return false
        }
        return this._getHasValueContainsWordFilterFunction(
          cellValue,
          filterValue
        )
      }
    },
  }
)

export const hasMultipleSelectAnyOptionIdEqualMixin = Object.assign(
  {},
  hasValueEqualFilterMixin,
  {
    getHasValueEqualFilterFunction(field) {
      return (cellValue, filterValue) => {
        if (!Array.isArray(cellValue)) {
          return false
        }
        const rowValueIds = new Set(
          cellValue.flatMap((v) => (v?.value || []).map((i) => i.id))
        )
        const filterValues = (filterValue || '')
          .trim()
          .split(',')
          .map(Number.parseInt)
        return filterValues.some((fltValue) => rowValueIds.has(fltValue))
      }
    },
  }
)

export const hasMultipleSelectOptionIdEqualMixin = Object.assign(
  {},
  hasValueEqualFilterMixin,
  {
    _getHasValueEqualFilterFunctionForRowValues(rowValueIdSets, filterValues) {
      // Compare if any of the linked row values match exactly the filter values
      return rowValueIdSets.some((rowValueIdSet) =>
        _.isEqual(rowValueIdSet, new Set(filterValues))
      )
    },

    getHasValueEqualFilterFunction(field) {
      return (cellValue, filterValue) => {
        if (!Array.isArray(cellValue)) {
          return false
        }

        const filterValues = (filterValue || '')
          .trim()
          .split(',')
          .map((oid) => Number.parseInt(oid))

        // create an array with the sets containing the ids per linked row
        const rowValueIdSets = cellValue.map(
          (v) => new Set(v?.value.map((i) => i.id))
        )
        return this._getHasValueEqualFilterFunctionForRowValues(
          rowValueIdSets,
          filterValues
        )
      }
    },
  }
)
