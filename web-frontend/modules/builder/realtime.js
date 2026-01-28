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

    store.dispatch('element/forceCreate', {
      page: ctx.page,
      element: data.element,
      beforeId: data.before_id,
    })
  })

  realtime.registerEvent('element_deleted', ({ store }, data) => {
    const ctx = getPageContext(store, data.page_id)
    if (!ctx) return

    store.dispatch('element/forceDelete', {
      builder: ctx.builder,
      page: ctx.page,
      elementId: data.element_id,
    })
  })

  realtime.registerEvent('element_updated', ({ store }, { element }) => {
    const ctx = getPageContext(store, element.page_id)
    if (!ctx) return

    store.dispatch('element/forceUpdate', {
      builder: ctx.builder,
      page: ctx.page,
      element,
      values: element,
    })
  })

  realtime.registerEvent('element_moved', ({ store }, data) => {
    const ctx = getPageContext(store, data.page_id)
    if (!ctx) return

    store.dispatch('element/forceMove', {
      builder: ctx.builder,
      page: ctx.page,
      elementId: data.element_id,
      beforeElementId: data.before_id,
      parentElementId: data.parent_element_id,
      placeInContainer: data.place_in_container,
    })
  })

  realtime.registerEvent(
    'element_orders_recalculated',
    ({ store, app }, data) => {
      const selectedPage = store.getters['page/getSelected']
      const builder = store.getters['application/getById'](
        selectedPage.builder_id
      )
      if (generateHash(selectedPage.id) === data.page_id) {
        store.dispatch('element/fetch', {
          builder,
          page: selectedPage,
        })
      }
    }
  )

  realtime.registerEvent('elements_moved', ({ store }, { elements }) => {
    elements.forEach((element) => {
      const ctx = getPageContext(store, element.page_id)
      if (!ctx) return

      store.dispatch('element/forceUpdate', {
        builder: ctx.builder,
        page: ctx.page,
        element,
        values: {
          order: element.order,
          place_in_container: element.place_in_container,
        },
      })
    })
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
