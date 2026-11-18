import { ulid } from 'ulid'

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

/** Preserve literal defaults while supporting multiple dropdown selections. */
export const getTextFilterDefaultValue = (widget) => {
  const value = widget.default_value ?? ''
  const values = Array.isArray(value) ? value : value ? [value] : []
  return widget.mode === 'dropdown' && widget.multiple === true
    ? values
    : values[0] || ''
}

/** Matches the backend limit on a dispatched filter value. */
export const TEXT_FILTER_MAX_VALUE_LENGTH = 1000

/**
 * Operators a filter set up from a field uses, in order of preference. Keep in
 * sync with `DEFAULT_OPERATORS` in the backend's `filter_setup.py`.
 */
export const DEFAULT_FILTER_OPERATORS = [
  'single_select_is_any_of',
  'multiple_select_has',
  'contains',
  'equal',
]

export const getDefaultFilterOperator = (registry, field) =>
  DEFAULT_FILTER_OPERATORS.find((type) =>
    registry.get('viewFilter', type).fieldIsCompatible(field)
  ) || null

/**
 * The field a filter starts on for a table: its primary field, else the first
 * one in the table's order that a filter can match. Like the backend's choice.
 */
export const getFirstFilterField = (registry, fields) =>
  [...fields]
    .sort(
      (a, b) =>
        Number(Boolean(b.primary)) - Number(Boolean(a.primary)) ||
        (a.order ?? 0) - (b.order ?? 0) ||
        a.id - b.id
    )
    .find((field) => getDefaultFilterOperator(registry, field)) || null

/**
 * A link matching the filter widget's value against any of the fields, like
 * the backend builds for a filter's fields. Null when no field can be matched.
 */
export const buildFieldsFilterLink = (
  registry,
  filterWidget,
  targetId,
  fields
) => {
  const filters = fields.flatMap((field) => {
    const type = getDefaultFilterOperator(registry, field)
    return type
      ? [
          {
            id: ulid(),
            field: field.id,
            type,
            group: null,
            value: {
              formula: `get('widget_data.${filterWidget.id}')`,
              mode: 'simple',
              version: '0.1',
            },
          },
        ]
      : []
  })
  return filters.length
    ? {
        target_widget_id: targetId,
        enabled: true,
        empty_behavior: 'apply_nothing',
        group: { filter_type: 'OR', filter_groups: [], filters },
      }
    : null
}

/** Filter widgets currently applied to the target widget. */
export const getFiltersOfWidget = (widgets, targetWidgetId, registry) =>
  widgets.filter((owner) => {
    const type = registry.get('dashboardWidget', owner.type)
    return (
      type.isFilterWidget &&
      type.getTargetWidgetIds(owner).includes(targetWidgetId)
    )
  })
