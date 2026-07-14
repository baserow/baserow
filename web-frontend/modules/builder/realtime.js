import { generateHash } from '@baserow/modules/core/utils/hashing'

/**
 * Returns the matching page and builder for a given page ID.
 * Checks both the selected page and the shared page.
 */
const getPageContext = (store, pageId) => {
  const selectedPage = store.getters['page/getSelected']
  const builder = store.getters['application/get'](selectedPage?.builder_id)
  if (!builder) return null // Sometimes we don't have the builder somehow

  const sharedPage = store.getters['page/getSharedPage'](builder)
  const pages = [selectedPage, sharedPage]
  const page = pages.find((p) => p?.id === pageId)
  if (!page) return null

  return { page, builder, pages }
}

/**
 * Returns the application (builder) for a given application ID, or null when it isn't
 * loaded in the store. Used by the integration and user source realtime handlers,
 * which are scoped to the application rather than a page.
 */
const getApplicationContext = (store, applicationId) => {
  const application = store.getters['application/get'](applicationId)
  if (!application) return null
  return { application }
}

export const registerRealtimeEvents = (realtime) => {
  // Page events
  realtime.registerEvent('page_created', ({ store }, data) => {
    const builder = store.getters['application/get'](data.page.builder_id)
    store.dispatch('page/forceCreate', { builder, page: data.page })
  })

  realtime.registerEvent('page_updated', ({ store }, data) => {
    const builder = store.getters['application/get'](data.page.builder_id)
    if (builder !== undefined) {
      const page = store.getters['page/getAllPages'](builder).find(
        (p) => p.id === data.page.id
      )
      if (page !== undefined) {
        store.dispatch('page/forceUpdate', {
          builder,
          page,
          values: data.page,
        })
      }
    }
  })

  realtime.registerEvent('page_deleted', ({ store }, data) => {
    const builder = store.getters['application/get'](data.builder_id)
    if (builder !== undefined) {
      const page = store.getters['page/getAllPages'](builder).find(
        (p) => p.id === data.page_id
      )
      if (page !== undefined) {
        store.dispatch('page/forceDelete', {
          builder,
          page,
        })
      }
    }
  })

  realtime.registerEvent('pages_reordered', ({ store, app }, data) => {
    const builder = store.getters['application/getAll'].find(
      (application) => generateHash(application.id) === data.builder_id
    )
    if (builder !== undefined) {
      store.commit('page/ORDER_PAGES', {
        builder,
        order: data.order,
        isHashed: true,
      })
    }
  })

  // Element events
  realtime.registerEvent('element_created', ({ store }, data) => {
    const ctx = getPageContext(store, data.element.page_id)
    if (!ctx) return

    // Update the graph first so forceCreate's fallback sees the element already
    // in the correct position and skips the end-of-chain append.
    if (data.graph) {
      store.dispatch('page/forceUpdate', {
        page: ctx.page,
        values: { graph: data.graph },
      })
    }

    store.dispatch('element/forceCreate', {
      page: ctx.page,
      element: data.element,
    })
  })

  realtime.registerEvent('elements_created', ({ store }, data) => {
    const ctx = getPageContext(store, data.page_id)
    if (!ctx) return

    if (data.graph) {
      store.dispatch('page/forceUpdate', {
        page: ctx.page,
        values: { graph: data.graph },
      })
    }

    for (const element of data.elements) {
      store.dispatch('element/forceCreate', {
        page: ctx.page,
        element,
      })
    }

    for (const workflowAction of data.workflow_actions || []) {
      store.dispatch('builderWorkflowAction/forceCreate', {
        page: ctx.page,
        workflowAction,
      })
    }
  })

  realtime.registerEvent('element_deleted', ({ store }, data) => {
    const ctx = getPageContext(store, data.page_id)
    if (!ctx) return

    // Remove the deleted element and its whole subtree's records...
    const elementIds = data.element_ids ?? [data.element_id]
    for (const elementId of elementIds) {
      store.dispatch('element/forceDelete', {
        builder: ctx.builder,
        page: ctx.page,
        elementId,
      })
    }

    // ...then apply the relinked graph so the remaining siblings/children of the
    // deleted element stay connected (forceDelete doesn't touch the graph).
    if (data.graph) {
      store.dispatch('page/forceUpdate', {
        page: ctx.page,
        values: { graph: data.graph },
      })
    }
  })

  realtime.registerEvent('element_updated', ({ store }, { element }) => {
    const ctx = getPageContext(store, element.page_id)
    if (!ctx) return

    store.dispatch('element/forceUpdate', {
      builder: ctx.builder,
      page: ctx.page,
      element,
      values: element,
      viaRealtime: true,
    })
  })

  realtime.registerEvent('element_moved', ({ store }, data) => {
    // Cross-page move: the element (and any descendants that travelled with it)
    // left the source page for the target page. Relocate the records and apply
    // both pages' refreshed graphs. Same-page moves omit these fields.
    if (data.source_page_id != null && data.source_page_id !== data.page_id) {
      const sourceCtx = getPageContext(store, data.source_page_id)
      const targetCtx = getPageContext(store, data.page_id)

      // Remove the moved elements from the source page (only if it's loaded —
      // a client viewing another page won't have it) and refresh its graph.
      if (sourceCtx) {
        for (const element of data.elements) {
          store.dispatch('element/forceDelete', {
            builder: sourceCtx.builder,
            page: sourceCtx.page,
            elementId: element.id,
          })
        }
        // The moved elements' workflow actions travel with them, so remove them
        // from the source page too (their page foreign key now points elsewhere).
        for (const workflowAction of data.workflow_actions || []) {
          store.dispatch('builderWorkflowAction/forceDelete', {
            page: sourceCtx.page,
            workflowActionId: workflowAction.id,
          })
        }
        store.dispatch('page/forceUpdate', {
          page: sourceCtx.page,
          values: { graph: data.source_graph },
        })
      }

      // Add the moved elements to the target page. Apply the graph first so
      // forceCreate sees them already positioned and skips the root-chain append.
      if (targetCtx) {
        store.dispatch('page/forceUpdate', {
          page: targetCtx.page,
          values: { graph: data.graph },
        })
        for (const element of data.elements) {
          store.dispatch('element/forceCreate', {
            page: targetCtx.page,
            element,
          })
        }
        // Re-add the workflow actions on the target page so they stay associated
        // with their (now relocated) elements.
        for (const workflowAction of data.workflow_actions || []) {
          store.dispatch('builderWorkflowAction/forceCreate', {
            page: targetCtx.page,
            workflowAction,
          })
        }
      }
      return
    }

    const ctx = getPageContext(store, data.page_id)
    if (!ctx) return

    store.dispatch('page/forceUpdate', {
      page: ctx.page,
      values: { graph: data.graph },
    })
    store.dispatch('element/refreshCachedValues', { page: ctx.page })
  })

  realtime.registerEvent('elements_moved', ({ store }, { page_id, graph }) => {
    const ctx = getPageContext(store, page_id)
    if (!ctx) return

    store.dispatch('page/forceUpdate', { page: ctx.page, values: { graph } })
    store.dispatch('element/refreshCachedValues', { page: ctx.page })
  })

  // Data source events
  realtime.registerEvent('data_source_created', ({ store }, data) => {
    const ctx = getPageContext(store, data.data_source.page_id)
    if (!ctx) return

    store.dispatch('dataSource/forceCreate', {
      page: ctx.page,
      dataSource: data.data_source,
      beforeId: data.before_id,
    })
  })

  realtime.registerEvent('data_source_updated', ({ store }, data) => {
    const ctx = getPageContext(store, data.data_source.page_id)
    if (!ctx) return

    const dataSource = store.getters['dataSource/getPagesDataSourceById'](
      ctx.pages,
      data.data_source.id
    )
    if (!dataSource) return

    // The data source may currently live on a different page than the event's
    // page_id (e.g. sharing/un-sharing — including via undo/redo — moves it
    // between a content page and the shared page). Relocate it to the destination
    // page first, otherwise forceUpdate would duplicate it across both page lists.
    if (dataSource.page_id !== data.data_source.page_id) {
      const sourcePage = ctx.pages.find((p) => p?.id === dataSource.page_id)
      if (sourcePage) {
        store.dispatch('dataSource/forcePageMove', {
          pageSource: sourcePage,
          pageDest: ctx.page,
          dataSourceId: dataSource.id,
        })
      }
    }

    store.dispatch('dataSource/forceUpdate', {
      page: ctx.page,
      dataSource,
      values: data.data_source,
    })
  })

  realtime.registerEvent('data_source_deleted', ({ store }, data) => {
    const ctx = getPageContext(store, data.page_id)
    if (!ctx) return

    store.dispatch('dataSource/forceDelete', {
      page: ctx.page,
      dataSourceId: data.data_source_id,
    })
  })

  // Integration events
  realtime.registerEvent('integration_created', ({ store }, data) => {
    const ctx = getApplicationContext(store, data.integration.application_id)
    if (!ctx) return

    store.dispatch('integration/forceCreate', {
      application: ctx.application,
      integration: data.integration,
      beforeId: data.before_id,
    })

    // When an integration is restored (e.g. undoing its deletion), re-dispatch
    // the data sources that reference it so their collection elements repopulate.
    // For a brand new integration this is a no-op (nothing references it yet).
    store.dispatch('dataSource/redispatchForIntegration', {
      builder: ctx.application,
      integrationId: data.integration.id,
    })
  })

  realtime.registerEvent('integration_updated', ({ store }, data) => {
    const ctx = getApplicationContext(store, data.integration.application_id)
    if (!ctx) return

    const integration = store.getters['integration/getIntegrationById'](
      ctx.application,
      data.integration.id
    )
    if (!integration) return

    store.dispatch('integration/forceUpdate', {
      application: ctx.application,
      integration,
      values: data.integration,
    })
  })

  realtime.registerEvent('integration_deleted', ({ store }, data) => {
    const ctx = getApplicationContext(store, data.application_id)
    if (!ctx) return

    store.dispatch('integration/forceDelete', {
      application: ctx.application,
      integrationId: data.integration_id,
    })

    // The integration's data sources are now misconfigured (their integration
    // can no longer be resolved). Re-dispatch them so collection elements bound
    // to those data sources reset their content (there are no records to show
    // while the integration is trashed). On restore the integration_created
    // event repopulates them.
    store.dispatch('dataSource/redispatchForIntegration', {
      builder: ctx.application,
      integrationId: data.integration_id,
    })
  })

  // User source events
  realtime.registerEvent('user_source_created', ({ store }, data) => {
    const ctx = getApplicationContext(store, data.user_source.application_id)
    if (!ctx) return

    store.dispatch('userSource/forceCreate', {
      application: ctx.application,
      userSource: data.user_source,
      beforeId: data.before_id,
    })
  })

  realtime.registerEvent('user_source_updated', ({ store }, data) => {
    const ctx = getApplicationContext(store, data.user_source.application_id)
    if (!ctx) return

    const userSource = store.getters['userSource/getUserSourceById'](
      ctx.application,
      data.user_source.id
    )
    if (!userSource) return

    store.dispatch('userSource/forceUpdate', {
      application: ctx.application,
      userSource,
      values: data.user_source,
    })
  })

  realtime.registerEvent('user_source_deleted', ({ store }, data) => {
    const ctx = getApplicationContext(store, data.application_id)
    if (!ctx) return

    store.dispatch('userSource/forceDelete', {
      application: ctx.application,
      userSourceId: data.user_source_id,
    })
  })

  // Workflow action events
  realtime.registerEvent('workflow_action_created', ({ store }, data) => {
    const ctx = getPageContext(store, data.page_id)
    if (!ctx) return

    store.dispatch('builderWorkflowAction/forceCreate', {
      page: ctx.page,
      workflowAction: data.workflow_action,
    })
  })

  realtime.registerEvent('workflow_action_updated', ({ store }, data) => {
    const ctx = getPageContext(store, data.page_id)
    if (!ctx) return

    store.dispatch('builderWorkflowAction/forceUpdate', {
      page: ctx.page,
      workflowAction: data.workflow_action,
      values: data.workflow_action,
      viaRealtime: true,
    })
  })

  realtime.registerEvent('workflow_action_deleted', ({ store }, data) => {
    const ctx = getPageContext(store, data.page_id)
    if (!ctx) return

    store.dispatch('builderWorkflowAction/forceDelete', {
      page: ctx.page,
      workflowActionId: data.workflow_action_id,
    })
  })

  realtime.registerEvent('workflow_actions_reordered', ({ store }, data) => {
    const ctx = getPageContext(store, data.page_id)
    if (!ctx) return

    store.dispatch('builderWorkflowAction/forceOrder', {
      page: ctx.page,
      order: data.order,
    })
  })

  // Theme events
  realtime.registerEvent('theme_updated', ({ store }, data) => {
    const builder = store.getters['application/get'](data.builder_id)
    if (!builder) return

    store.dispatch('theme/forceUpdate', {
      builder,
      values: data.properties,
    })
  })
}
