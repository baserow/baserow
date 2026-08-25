import { Registerable } from '@baserow/modules/core/registry'

/**
 * One copyable piece of view configuration. The actual copying is done by the
 * backend copy-configuration endpoint, so these registered types only provide
 * the UI metadata for the copy configuration modal, and `getType()` must
 * match a backend category type exactly. A view type declares which options
 * it supports via `ViewType.getCopyableViewConfigurationOptions()`, and an
 * option can only be copied when both the source and destination view type
 * declare it.
 */
export class CopyViewConfigurationOptionType extends Registerable {
  /**
   * The `destView` is provided so that the label can describe what the option
   * copies into this specific view.
   */
  getName(destView) {
    throw new Error('The name of a copy view configuration option must be set.')
  }

  /**
   * Additional check on top of both view types declaring the option, for
   * constraints that depend on the concrete source and destination view or
   * the workspace, a required license for example.
   */
  isEnabled(sourceView, destView, workspaceId) {
    return true
  }

  /**
   * Whether copying this option changes which rows are visible or how they
   * are ordered, so that an open destination view only refetches when it must.
   */
  refreshesRows() {
    return true
  }

  /**
   * Whether copying this option changes the view's field options, so that an
   * open destination view only refetches those when it must.
   */
  refreshesFieldOptions() {
    return false
  }
}

export class FieldVisibilityCopyOptionType extends CopyViewConfigurationOptionType {
  static getType() {
    return 'field_visibility'
  }

  getOrder() {
    return 10
  }

  getName() {
    return this.$t('copyViewConfigurationOption.fieldVisibility')
  }

  refreshesRows() {
    return false
  }

  refreshesFieldOptions() {
    return true
  }
}

export class FieldOrderCopyOptionType extends CopyViewConfigurationOptionType {
  static getType() {
    return 'field_order'
  }

  getOrder() {
    return 20
  }

  getName() {
    return this.$t('copyViewConfigurationOption.fieldOrder')
  }

  refreshesRows() {
    return false
  }

  refreshesFieldOptions() {
    return true
  }
}

export class FieldWidthsCopyOptionType extends CopyViewConfigurationOptionType {
  static getType() {
    return 'field_widths'
  }

  getOrder() {
    return 30
  }

  getName() {
    return this.$t('copyViewConfigurationOption.fieldWidths')
  }

  refreshesRows() {
    return false
  }

  refreshesFieldOptions() {
    return true
  }
}

export class ViewSettingsCopyOptionType extends CopyViewConfigurationOptionType {
  static getType() {
    return 'view_settings'
  }

  getOrder() {
    return 40
  }

  getName(destView) {
    // The copied attributes differ per view type, so the label enumerates the
    // destination's ones, the row height and frozen columns of a grid view for
    // example, because a plain "View settings" doesn't tell the user what will
    // be copied. The translation key is derived from the attribute name so
    // that a view type can add an attribute together with its own translation.
    const settings = this.app.$registry
      .get('view', destView.type)
      .getCopyableViewSettings()
      .map((attribute) => {
        const suffix = attribute
          .split('_')
          .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
          .join('')
        return this.$t(`copyViewConfigurationOption.viewSettings${suffix}`)
      })
    return this.$t('copyViewConfigurationOption.viewSettings', {
      settings: settings.join(', '),
    })
  }

  // The view components render these attributes, the grid row height and
  // frozen column count for example, reactively from the view object.
  refreshesRows() {
    return false
  }

  isEnabled(sourceView, destView, workspaceId) {
    // Only attributes that both view types declare are copied, so there must
    // be at least one in common.
    const registry = this.app.$registry
    const sourceSettings = registry
      .get('view', sourceView.type)
      .getCopyableViewSettings()
    return registry
      .get('view', destView.type)
      .getCopyableViewSettings()
      .some((attribute) => sourceSettings.includes(attribute))
  }
}

export class FiltersCopyOptionType extends CopyViewConfigurationOptionType {
  static getType() {
    return 'filters'
  }

  getOrder() {
    return 50
  }

  getName() {
    return this.$t('copyViewConfigurationOption.filters')
  }
}

export class SortsCopyOptionType extends CopyViewConfigurationOptionType {
  static getType() {
    return 'sorts'
  }

  getOrder() {
    return 60
  }

  getName() {
    return this.$t('copyViewConfigurationOption.sorts')
  }
}

export class GroupBysCopyOptionType extends CopyViewConfigurationOptionType {
  static getType() {
    return 'group_bys'
  }

  getOrder() {
    return 70
  }

  getName() {
    return this.$t('copyViewConfigurationOption.groupBys')
  }
}

export class DecorationsCopyOptionType extends CopyViewConfigurationOptionType {
  static getType() {
    return 'decorations'
  }

  getOrder() {
    return 80
  }

  getName() {
    return this.$t('copyViewConfigurationOption.decorations')
  }

  // Decorations only change how the already loaded rows are decorated.
  refreshesRows() {
    return false
  }

  isEnabled(sourceView, destView, workspaceId) {
    // Deactivated decorator types, because the workspace has no premium
    // license for example, are excluded so that the copy can't fail on the
    // backend's license check.
    return Object.values(this.app.$registry.getAll('viewDecorator')).some(
      (decoratorType) =>
        !decoratorType.isDeactivated(workspaceId) &&
        decoratorType.isCompatible(sourceView) &&
        decoratorType.isCompatible(destView)
    )
  }
}

export class DefaultRowValuesCopyOptionType extends CopyViewConfigurationOptionType {
  static getType() {
    return 'default_row_values'
  }

  getOrder() {
    return 90
  }

  getName() {
    return this.$t('copyViewConfigurationOption.defaultRowValues')
  }

  // Default row values only affect newly created rows.
  refreshesRows() {
    return false
  }
}
