import isEqual from 'lodash/isEqual'

/** Viewer values changed automatically by an optimistic widget settings save. */
export class WidgetValueUpdate {
  constructor(previousValue, updatedValue) {
    this.originalValue = previousValue
    this.updatedValue = updatedValue
  }

  merge(previousValue, updatedValue) {
    // A viewer can change the selection between two coalesced settings edits.
    if (!isEqual(previousValue, this.updatedValue)) {
      this.originalValue = previousValue
    }
    this.updatedValue = updatedValue
  }

  restore(context, registry, widgetId) {
    if (
      isEqual(this.originalValue, this.updatedValue) ||
      !isEqual(context.state.widgetValues[widgetId], this.updatedValue)
    )
      return
    const widget = context.state.widgets.find(({ id }) => id === widgetId)
    const type = widget && registry.get('dashboardWidget', widget.type)
    if (type?.isFilterWidget) {
      type.valueChanged(
        widget,
        { ...context, registry },
        type.getDefaultValue({
          ...widget,
          default_value: this.originalValue,
        })
      )
    }
  }
}
