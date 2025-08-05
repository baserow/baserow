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
}
