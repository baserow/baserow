import ApplicationService from '@baserow/modules/core/services/application'
import ViewService from '@baserow/modules/database/services/view'
import { waitFor } from '@baserow/modules/core/utils/queue'

const BROADCAST_WAIT_MS = 3000

/**
 * @typedef {object} NavigationTarget
 * @property {number} [applicationId] The application holding the target.
 * @property {function(object): object|undefined} [findTarget]
 * @property {function(object, object): Promise<void>} [addTarget]
 * @property {function(): boolean} [isReady] Other state the route needs.
 * @property {function(): Promise<void>} [loadReady] Fetches that state.
 * @property {import('vue-router').RouteLocationRaw} route
 */

/** @returns {NavigationTarget} */
function tableTarget({ $store, $client }, workspaceId, location) {
  const viewsLoaded = () => $store.state.view.tableId === location.table_id
  return {
    applicationId: location.database_id,
    findTarget: (database) =>
      database.tables.find((table) => table.id === location.table_id),
    addTarget: (database, table) =>
      $store.dispatch('table/forceUpsert', { database, data: table }),
    // Opening a table fetches its views unless the store already has them.
    isReady: () =>
      !location.view_id ||
      !viewsLoaded() ||
      Boolean($store.getters['view/get'](location.view_id)),
    loadReady: async () => {
      const { data } = await ViewService($client).get(
        location.view_id,
        true,
        true,
        true,
        true,
        true
      )
      if (viewsLoaded() && data.table_id === location.table_id) {
        await $store.dispatch('view/forceCreate', { data })
      }
    },
    route: {
      name: 'database-table',
      params: {
        workspaceId,
        databaseId: location.database_id,
        tableId: location.table_id,
        viewId: location.view_id,
      },
    },
  }
}

/** Each built-in location supplies only its target and route; loading is shared. */
const NAVIGATION_TARGETS = Object.freeze({
  'database-table': tableTarget,
  'database-view': tableTarget,
  'builder-page': ({ $store }, workspaceId, location) => ({
    applicationId: location.application_id,
    findTarget: (builder) =>
      builder.pages.find((page) => page.id === location.page_id),
    addTarget: (builder, page) =>
      $store.dispatch('page/forceCreate', { builder, page }),
    route: {
      name: 'builder-page',
      params: { builderId: location.application_id, pageId: location.page_id },
    },
  }),
  'automation-workflow': ({ $store }, workspaceId, location) => ({
    applicationId: location.automation_id,
    findTarget: (automation) =>
      automation.workflows.find(
        (workflow) => workflow.id === location.workflow_id
      ),
    addTarget: (automation, workflow) =>
      $store.dispatch('automationWorkflow/forceCreate', {
        automation,
        workflow,
      }),
    route: {
      name: 'automation-workflow',
      params: {
        automationId: location.automation_id,
        workflowId: location.workflow_id,
      },
    },
  }),
  dashboard: (app, workspaceId, location) => ({
    applicationId: location.dashboard_id,
    findTarget: (dashboard) => dashboard,
    route: {
      name: 'dashboard-application',
      params: { dashboardId: location.dashboard_id },
    },
  }),
  workspace: (app, workspaceId) => ({
    route: { name: 'workspace', params: { workspaceId } },
  }),
})

/**
 * Wait for realtime delivery, then fetch once if the broadcast is late. A busy
 * worker may be running Kuma instead of delivering its resource broadcasts.
 *
 * @param {function(): boolean} check
 * @param {function(): Promise<void>} load
 * @param {function(): boolean} isCurrent
 * @returns {Promise<boolean>} Whether the current navigation can proceed.
 */
async function ensureReady(check, load, isCurrent) {
  try {
    await waitFor(() => !isCurrent() || check(), 5, BROADCAST_WAIT_MS)
  } catch {
    if (!isCurrent()) return false
    try {
      await load()
    } catch (error) {
      if (!error.handler && !error.response) throw error
      return false
    }
  }
  return isCurrent() && Boolean(check())
}

/** @param {NavigationTarget} target */
async function loadTarget({ $store, $client }, target, isCurrent) {
  const { data } = await ApplicationService($client).get(target.applicationId)
  if (!isCurrent()) return
  const application = $store.getters['application/get'](target.applicationId)
  if (!application) {
    await $store.dispatch('application/forceCreate', data)
    return
  }
  const resource = target.findTarget(data)
  if (resource && !target.findTarget(application)) {
    await target.addTarget(application, resource)
  }
}

/**
 * Open one of Kuma's locations once the store has the resources the route needs.
 * A superseded or closed panel never navigates after an asynchronous load.
 *
 * @param {object} app The panel's store, client, registry and router.
 * @param {number} workspaceId The sending workspace.
 * @param {object} location The location sent by Kuma's navigation tool.
 * @param {function(): boolean} isCurrent Whether this navigation still owns the UI.
 * @returns {Promise<void>}
 */
export async function navigateToAssistantLocation(
  app,
  workspaceId,
  location,
  isCurrent
) {
  if (!isCurrent() || !Object.hasOwn(NAVIGATION_TARGETS, location.type)) return
  if (location.type === 'database-view') {
    const viewType = app.$registry.get('view', location.view_type)
    if (!viewType || viewType.isDeactivated(workspaceId)) return
  }
  const target = NAVIGATION_TARGETS[location.type](app, workspaceId, location)
  if (target.applicationId) {
    const findStoredTarget = () => {
      const application = app.$store.getters['application/get'](
        target.applicationId
      )
      return application && target.findTarget(application)
    }
    if (
      !(await ensureReady(
        findStoredTarget,
        () => loadTarget(app, target, isCurrent),
        isCurrent
      ))
    ) {
      return
    }
  }
  if (
    target.isReady &&
    !(await ensureReady(target.isReady, target.loadReady, isCurrent))
  ) {
    return
  }
  if (isCurrent()) await app.$router.push(target.route)
}
