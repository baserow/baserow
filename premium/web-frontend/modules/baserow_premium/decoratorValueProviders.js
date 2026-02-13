import { DecoratorValueProviderType } from '@baserow/modules/database/decoratorValueProviders'

import SingleSelectColorValueProviderForm from '@baserow_premium/components/views/SingleSelectColorValueProviderForm'
import ConditionalColorValueProviderForm from '@baserow_premium/components/views/ConditionalColorValueProviderForm'
import {
  BackgroundColorViewDecoratorType,
  LeftBorderColorViewDecoratorType,
} from '@baserow_premium/viewDecorators'
import { uuid } from '@baserow/modules/core/utils/string'
import { randomColor } from '@baserow/modules/core/utils/colors'
import { matchSearchFilters } from '@baserow/modules/database/utils/view'

export class SingleSelectColorValueProviderType extends DecoratorValueProviderType {
  static getType() {
    return 'single_select_color'
  }

  getName() {
    const { $i18n } = this.app
    return $i18n.t('decoratorValueProviderType.singleSelectColor')
  }

  getDescription() {
    const { $i18n } = this.app
    return $i18n.t('decoratorValueProviderType.singleSelectColorDescription')
  }

  getIconClass() {
    return 'baserow-icon-single-select'
  }

  getFormComponent() {
    return SingleSelectColorValueProviderForm
  }

  getCompatibleDecoratorTypes() {
    return [LeftBorderColorViewDecoratorType, BackgroundColorViewDecoratorType]
  }

  getValue({ options, fields, row }) {
    const value = row[`field_${options.field_id}`]
    return value?.color || ''
  }

  getDefaultConfiguration({ fields }) {
    const firstSelectField = fields.find(({ type }) => type === 'single_select')
    return {
      field_id: firstSelectField?.id || null,
    }
  }
}

export class ConditionalColorValueProviderType extends DecoratorValueProviderType {
  static getType() {
    return 'conditional_color'
  }

  static getDefaultFilterConf(registry, { fields, filterGroupId = null }) {
    for (const field of fields) {
      const filter = { field: field.id }

      const viewFilterTypes = registry.getAll('viewFilter')
      const compatibleType = Object.values(viewFilterTypes).find(
        (viewFilterType) => {
          return viewFilterType.fieldIsCompatible(field)
        }
      )
      if (!compatibleType) {
        continue
      }

      filter.type = compatibleType.type
      const viewFilterType = registry.get('viewFilter', filter.type)
      filter.value = viewFilterType.getDefaultValue(field)
      filter.preload_values = {}
      filter.id = uuid()
      filter.group = filterGroupId

      return filter
    }
  }

  static getDefaultFilterGroupConf(groupId = null, parentGroupId = null) {
    return {
      filter_type: 'AND',
      id: groupId || uuid(),
      parent_group: parentGroupId,
    }
  }

  static getDefaultColorConf(excludeColors = undefined) {
    return {
      color: randomColor(excludeColors),
      operator: 'AND',
      filters: [],
      id: uuid(),
    }
  }

  getName() {
    const { $i18n } = this.app
    return $i18n.t('decoratorValueProviderType.conditionalColor')
  }

  getDescription() {
    const { $i18n } = this.app
    return $i18n.t('decoratorValueProviderType.conditionalColorDescription')
  }

  getIconClass() {
    return 'iconoir-filter'
  }

  getValue({ options, fields, row }) {
    for (const {
      color,
      filters,
      operator,
      filter_groups: filterGroups,
    } of options.colors) {
      if (
        row.id !== -1 &&
        row.id !== undefined &&
        matchSearchFilters(operator, filters, filterGroups, fields, row)
      ) {
        return color
      }
    }
    return ''
  }

  getCompatibleDecoratorTypes() {
    return [LeftBorderColorViewDecoratorType, BackgroundColorViewDecoratorType]
  }

  getFormComponent() {
    return ConditionalColorValueProviderForm
  }

  getDefaultConfiguration() {
    return {
      default: null,
      colors: [ConditionalColorValueProviderType.getDefaultColorConf()],
    }
  }
}
