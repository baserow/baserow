import isEqual from 'lodash/isEqual'

/** Viewer values changed automatically by an optimistic widget settings save. */
export class WidgetValueUpdate {
  constructor(previousValue, updatedValue, selection) {
    this.originalValue = previousValue
    this.updatedValue = updatedValue
    this.selection = selection
  }

  merge(previousValue, updatedValue, selection) {
    // A viewer can change the selection between two coalesced settings edits.
    if (selection !== this.selection) {
      this.originalValue = previousValue
    }
    this.updatedValue = updatedValue
    this.selection = selection
  }

  restore(context, registry, widgetId) {
    const selection = context.state.widgetSelections[widgetId]
    let value
    if (selection !== this.selection) {
      // Preserve later user choices, including a clear, even if restoring the
      // configuration just applied a nonempty default to that empty selection.
      value = selection?.value
    } else {
      if (
        isEqual(this.originalValue, this.updatedValue) ||
        !isEqual(context.state.widgetValues[widgetId], this.updatedValue)
      )
        return
      value = this.originalValue
    }
    const widget = context.state.widgets.find(({ id }) => id === widgetId)
    const type = widget && registry.get('dashboardWidget', widget.type)
    if (type?.isFilterWidget) {
      type.valueChanged(
        widget,
        { ...context, registry },
        type.getDefaultValue({
          ...widget,
          default_value: value,
        })
      )
    }
  }
}
