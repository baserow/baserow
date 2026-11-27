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

/** Read the configured conditions contributed by each filter widget to a target. */
export const getWidgetFilterGroups = (
  widgets,
  targetWidgetId,
  registry,
  excludedOwnerId = null
) => {
  if (targetWidgetId == null) return []

  const groups = []
  for (const owner of widgets) {
    if (
      owner.id === excludedOwnerId ||
      !registry.get('dashboardWidget', owner.type).isFilterWidget
    )
      continue

    const contribution = (owner.target_filters || []).find(
      (link) => link.target_widget_id === targetWidgetId
    )
    if (!contribution || contribution.enabled === false) continue

    const alternativeGroup =
      contribution.empty_behavior === 'apply_alternative' &&
      contribution.alternative_group?.filters?.length
        ? contribution.alternative_group
        : null
    if (!contribution.group?.filters?.length && !alternativeGroup) continue

    groups.push({
      key: owner.id,
      title: owner.title,
      group: contribution.group,
      alternativeGroup,
      owner,
    })
  }
  return groups
}

export const countFilterGroupConditions = (groups) =>
  groups.reduce(
    (count, { group, alternativeGroup }) =>
      count +
      (group?.filters?.length || 0) +
      (alternativeGroup?.filters?.length || 0),
    0
  )

export const isTextFilterNumberInput = (widget) =>
  widget.mode !== 'dropdown' && widget.input_format === 'number'

/** Keep the exact decimal as text, so formulas and large numbers retain precision. */
export const normalizeTextFilterNumber = (value) => {
  if (value === '') return ''
  const number = value.trim()
  return /^[+-]?(?:[0-9]+(?:[.,][0-9]+)?|[.,][0-9]+)$/.test(number)
    ? number.replace(',', '.')
    : null
}

/** Preserve literal defaults while supporting multiple dropdown selections. */
export const getTextFilterDefaultValue = (widget) => {
  const value = widget.default_value ?? ''
  const values = Array.isArray(value) ? value : value ? [value] : []
  if (widget.mode === 'dropdown' && widget.multiple === true) return values
  const single = values[0] || ''
  return isTextFilterNumberInput(widget)
    ? (normalizeTextFilterNumber(single) ?? '')
    : single
}

/** Matches the backend limit on a dispatched filter value. */
export const TEXT_FILTER_MAX_VALUE_LENGTH = 1000

/** Filter widgets currently applied to the target widget. */
export const getFiltersOfWidget = (widgets, targetWidgetId, registry) =>
  widgets.filter((owner) => {
    const type = registry.get('dashboardWidget', owner.type)
    return (
      type.isFilterWidget &&
      type.getTargetWidgetIds(owner).includes(targetWidgetId)
    )
  })
