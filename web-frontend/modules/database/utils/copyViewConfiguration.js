import ViewService from '@baserow/modules/database/services/view'

/**
 * The copy view configuration options offered when copying into the given destination
 * view, sorted by order. Options the destination view type can never receive are not
 * included.
 */
export function getDestinationCopyOptions(registry, destView) {
  return registry
    .get('view', destView.type)
    .getCopyableViewConfigurationOptions()
    .sort((a, b) => a.getOrder() - b.getOrder())
}

/**
 * The option keys that are enabled for the concrete source and destination view pair:
 * the intersection of both view types' option keys, refined by each option's own
 * `isEnabled` check.
 */
export function getEnabledCopyOptionKeys(
  registry,
  sourceView,
  destView,
  workspaceId
) {
  const sourceKeys = new Set(
    registry
      .get('view', sourceView.type)
      .getCopyableViewConfigurationOptions()
      .map((option) => option.getType())
  )
  return getDestinationCopyOptions(registry, destView)
    .filter(
      (option) =>
        sourceKeys.has(option.getType()) &&
        option.isEnabled(sourceView, destView, workspaceId)
    )
    .map((option) => option.getType())
}

/**
 * The views that can act as the source of a configuration copy into the given
 * destination view: every other view that has at least one enabled option in common
 * with the destination. When this is empty, the copy configuration modal would be a
 * dead end and shouldn't be offered at all, for a form view or a table with a single
 * view for example.
 */
export function getCompatibleSourceViews(
  registry,
  views,
  destView,
  workspaceId
) {
  return views.filter(
    (view) =>
      view.id !== destView.id &&
      getEnabledCopyOptionKeys(registry, view, destView, workspaceId).length > 0
  )
}

/**
 * Whether the destination view must refetch its rows and/or field options
 * after the given categories have been copied into it, so that both the
 * initiating client and the realtime event handler make the same
 * option-driven refresh decision.
 */
export function getRefreshFlags(registry, destView, categories) {
  const appliedOptions = getDestinationCopyOptions(registry, destView).filter(
    (option) => categories.includes(option.getType())
  )
  return {
    refreshRows: appliedOptions.some((option) => option.refreshesRows()),
    includeFieldOptions: appliedOptions.some((option) =>
      option.refreshesFieldOptions()
    ),
  }
}

/**
 * Applies a complete new view payload, filters, sortings, group bys, decorations and
 * scalar properties included, to the view store in a single mutation, and refreshes
 * the table once if the view is currently open. Used after the copy configuration
 * endpoint responds and by the matching realtime event, so both paths behave
 * identically and the open view updates without flickering.
 */
export async function forceUpdateViewConfiguration(
  { $store, $bus },
  view,
  values,
  { refreshRows = true, includeFieldOptions = true } = {}
) {
  await $store.dispatch('view/forceUpdate', {
    view,
    values,
    repopulate: true,
  })

  if (
    (refreshRows || includeFieldOptions) &&
    $store.getters['view/getSelectedId'] === view.id
  ) {
    $bus.$emit('table-refresh', {
      tableId: view.table_id,
      includeFieldOptions,
    })
  }
}

/**
 * Copies the checked configuration options of the source view into the destination
 * view via the backend endpoint. The whole copy is a single undoable action, and the
 * store is only updated once the endpoint responds, so the open view never shows a
 * partially copied configuration. Both views must belong to the same table.
 */
export async function copyViewConfiguration(
  { $store, $client, $registry, $bus },
  { sourceView, destView, categories, workspaceId }
) {
  const enabledKeys = getEnabledCopyOptionKeys(
    $registry,
    sourceView,
    destView,
    workspaceId
  )
  categories = categories.filter((category) => enabledKeys.includes(category))

  const { data } = await ViewService($client).copyConfiguration(destView.id, {
    sourceViewId: sourceView.id,
    categories,
  })

  await forceUpdateViewConfiguration(
    { $store, $bus },
    destView,
    data,
    getRefreshFlags($registry, destView, categories)
  )
}
