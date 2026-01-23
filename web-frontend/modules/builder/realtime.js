import { generateHash } from '@baserow/modules/core/utils/hashing'

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
    const selectedPage = store.getters['page/getSelected']
    if (selectedPage.id === data.element.page_id) {
      store.dispatch('element/forceCreate', {
        page: selectedPage,
        element: data.element,
        beforeId: data.before_id,
      })
    }
  })

  realtime.registerEvent('element_deleted', ({ store }, data) => {
    const selectedPage = store.getters['page/getSelected']
    if (selectedPage.id === data.page_id) {
      const builder = store.getters['application/get'](selectedPage.builder_id)
      if (builder) {
        // Sometimes we don't have the builder somehow
        store.dispatch('element/forceDelete', {
          builder,
          page: selectedPage,
          elementId: data.element_id,
        })
      }
    }
  })

  realtime.registerEvent('element_updated', ({ store }, { element }) => {
    const selectedPage = store.getters['page/getSelected']
    if (selectedPage.id === element.page_id) {
      const builder = store.getters['application/get'](selectedPage.builder_id)
      if (builder) {
        // Sometimes we don't have the builder somehow
        store.dispatch('element/forceUpdate', {
          builder,
          page: selectedPage,
          element,
          values: element,
        })
      }
    }
  })

  realtime.registerEvent('element_moved', ({ store }, data) => {
    const selectedPage = store.getters['page/getSelected']
    if (selectedPage.id === data.page_id) {
      const builder = store.getters['application/get'](selectedPage.builder_id)
      if (builder) {
        // Sometimes we don't have the builder somehow
        store.dispatch('element/forceMove', {
          builder,
          page: selectedPage,
          elementId: data.element_id,
          beforeElementId: data.before_id,
          parentElementId: data.parent_element_id,
          placeInContainer: data.place_in_container,
        })
      }
    }
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

  realtime.registerEvent('elements_moved', ({ store, app }, { elements }) => {
    elements.forEach((element) => {
      const selectedPage = store.getters['page/getSelected']
      if (selectedPage.id === element.page_id) {
        const builder = store.getters['application/get'](
          selectedPage.builder_id
        )
        if (builder) {
          // Sometimes we don't have the builder somehow
          store.dispatch('element/forceUpdate', {
            builder,
            page: selectedPage,
            element,
            values: {
              order: element.order,
              place_in_container: element.place_in_container,
            },
          })
        }
      }
    })
  })

  // Data source events
  realtime.registerEvent('data_source_created', ({ store }, data) => {
    const selectedPage = store.getters['page/getSelected']
    if (selectedPage.id === data.data_source.page_id) {
      store.dispatch('dataSource/forceCreate', {
        page: selectedPage,
        dataSource: data.data_source,
        beforeId: data.before_id,
      })
    }
  })

  realtime.registerEvent('data_source_updated', ({ store }, data) => {
    const selectedPage = store.getters['page/getSelected']
    if (selectedPage.id === data.data_source.page_id) {
      const dataSource = store.getters['dataSource/getPageDataSources'](
        selectedPage
      ).find((ds) => ds.id === data.data_source.id)
      if (dataSource) {
        store.dispatch('dataSource/forceUpdate', {
          page: selectedPage,
          dataSource,
          values: data.data_source,
        })
      }
    }
  })

  realtime.registerEvent('data_source_deleted', ({ store }, data) => {
    const selectedPage = store.getters['page/getSelected']
    if (selectedPage.id === data.page_id) {
      store.dispatch('dataSource/forceDelete', {
        page: selectedPage,
        dataSourceId: data.data_source_id,
      })
    }
  })

  // Workflow action events
  realtime.registerEvent('workflow_action_created', ({ store }, data) => {
    const selectedPage = store.getters['page/getSelected']
    if (selectedPage.id === data.page_id) {
      store.dispatch('builderWorkflowAction/forceCreate', {
        page: selectedPage,
        workflowAction: data.workflow_action,
      })
    }
  })

  realtime.registerEvent('workflow_action_updated', ({ store }, data) => {
    const selectedPage = store.getters['page/getSelected']
    if (selectedPage.id === data.page_id) {
      const workflowAction = store.getters[
        'builderWorkflowAction/getWorkflowActions'
      ](selectedPage).find((wa) => wa.id === data.workflow_action.id)
      if (workflowAction) {
        store.dispatch('builderWorkflowAction/forceUpdate', {
          page: selectedPage,
          workflowAction,
          values: data.workflow_action,
        })
      }
    }
  })

  realtime.registerEvent('workflow_action_deleted', ({ store }, data) => {
    const selectedPage = store.getters['page/getSelected']
    if (selectedPage.id === data.page_id) {
      store.dispatch('builderWorkflowAction/forceDelete', {
        page: selectedPage,
        workflowActionId: data.workflow_action_id,
      })
    }
  })
}
