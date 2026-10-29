/** Derive affected sources directly from widget links in this dashboard store. */
export const refreshWidgetSources = (widget, { state, dispatch, registry }) => {
  const targets = new Set(
    registry.get('dashboardWidget', widget.type).getTargetWidgetIds(widget)
  )
  const sourceIds = new Set(
    state.widgets.flatMap((target) => {
      const type = registry.get('dashboardWidget', target.type)
      return type.isDisplayWidget && targets.has(target.id)
        ? [type.getDataSourceId(target)]
        : []
    })
  )
  dispatch(
    'refreshDataSources',
    state.dataSources
      .filter((source) => sourceIds.has(source.id))
      .map((source) => source.id)
  )
}
