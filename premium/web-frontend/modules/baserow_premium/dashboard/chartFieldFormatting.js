import { Registerable } from '@baserow/modules/core/registry'

export class ChartFieldFormattingType extends Registerable {
  constructor(...args) {
    super(...args)
    this.type = this.getType()

    if (this.type === null) {
      throw new Error('The type has to be set.')
    }
  }

  formatGroupByFieldValue(field, value) {
    return value ?? ''
  }
}

export class SingleSelectFormattingType extends ChartFieldFormattingType {
  static getType() {
    return 'single_select'
  }

  formatGroupByFieldValue(field, value) {
    if (value && typeof value === 'object') {
      return value.value ?? ''
    }

    const selectOption = field.select_options.find((item) => item.id === value)

    if (selectOption) {
      return selectOption.value
    }

    return value ?? ''
  }
}

export class MultipleSelectFormattingType extends SingleSelectFormattingType {
  static getType() {
    return 'multiple_select'
  }

  formatGroupByFieldValue(field, value) {
    if (value === null || value === undefined || value.length === 0) {
      return this.$t('chart.empty')
    }
    return value
      .map((option) => super.formatGroupByFieldValue(field, option))
      .join(', ')
  }
}
