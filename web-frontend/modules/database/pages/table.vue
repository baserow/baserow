<template>
  <div>
    <DefaultErrorPage v-if="dataError && !view?.id" :error="dataError" />

    <Table
      v-else
      :database="database"
      :table="table"
      :fields="fields"
      :views="views"
      :view="view"
      :view-error="dataError"
      :table-loading="loading"
      store-prefix="page/"
      @selected-view="selectedView"
      @selected-row="navigateToRowModal"
      @navigate-previous="(row, term) => setAdjacentRow(true, row, term)"
      @navigate-next="(row, term) => setAdjacentRow(false, row, term)"
    />
    <!--
      The child routes open modals that snapshot the fields when they're shown, so
      they can only mount once the fields of this table have been fetched.
    -->
    <NuxtPage
      v-if="hasChildRoute && !loading"
      :database="database"
      :table="table"
      :fields="fields"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { useHead } from '#imports'
import { usePageAsyncData } from '@baserow/modules/core/composables/usePageAsyncData'

import Table from '@baserow/modules/database/components/table/Table'
import DefaultErrorPage from '@baserow/modules/core/components/DefaultErrorPage'
import { StoreItemLookupError } from '@baserow/modules/core/errors'
import { normalizeError } from '@baserow/modules/database/utils/errors'
import { getDefaultView } from '@baserow/modules/database/utils/view'

definePageMeta({
  name: 'database-table',
  layout: 'app',
  middleware: [
    'settings',
    'authenticated',
    'workspacesAndApplications',
    // Selects the workspace, database and table of the route params. It only does
    // what must be done before the page can render, everything else is fetched by
    // the page itself, so that the skeleton loading state shows immediately.
    'selectWorkspaceDatabaseTable',
    'pendingJobs',
  ],
})

const route = useRoute()
const router = useRouter()
const nuxtApp = useNuxtApp()
const {
  $store,
  $realtime,
  $registry,
  $i18n: { t: $t },
} = nuxtApp

function finishLoading() {
  nuxtApp.callHook('page:loading:end')
}

// The database and table are selected by the `selectWorkspaceDatabaseTable`
// middleware, so they're there when the page renders. The views and fields arrive
// while the skeleton loading state is visible. They're read once instead of being
// computed, because the selection changes while this page is still rendered: the
// next route's middleware selects its own application before this page unmounts,
// and a realtime deletion of the database removes it from the store before the
// redirect away has finished.
const database = ref($store.getters['application/getSelected'])
const table = ref($store.getters['table/getSelected'])
const fields = computed(() => $store.getters['field/getAll'])
const views = computed(() => $store.state.view.items)

const { data, loading: fetching } = await usePageAsyncData(
  `database-table-page-${route.params.databaseId}-${route.params.tableId}-${route.params.viewId ?? 'null'}`,
  async () => {
    const currentTable = table.value
    const currentDatabase = database.value
    const viewId = route.params.viewId ? parseInt(route.params.viewId) : null
    const rowId = route.params.rowId ? parseInt(route.params.rowId) : null
    const result = { view: undefined }

    // The views only have to be fetched if the table changed, there is no need to
    // fetch them again when only the view or the row changes.
    const viewsLoadedForTable = $store.state.view.tableId === currentTable.id
    if (!viewsLoadedForTable) {
      await $store.dispatch('view/fetchAll', currentTable)
    }

    // Without a view in the route params the default one must be opened. The
    // redirect is returned because it can only be done once the page is rendered.
    if (viewId === null) {
      const defaultView = getDefaultView(
        nuxtApp,
        $store,
        currentDatabase.workspace.id,
        rowId !== null
      )
      if (defaultView) {
        result.redirect = {
          name: route.name,
          params: { ...route.params, viewId: defaultView.id },
          query: route.query,
        }
        return result
      }
    }

    // In some cases, the backend needs the view ID to scope which fields to list.
    // This can happen when a user does not have full access to a table for
    // example.
    const routeView = $store.getters['view/get'](viewId)
    let fieldsRequireViewId = false
    if (routeView) {
      const ownershipType = $registry.get(
        'viewOwnershipType',
        routeView.ownership_type
      )
      fieldsRequireViewId = ownershipType.fetchingFieldsRequiresViewId(
        currentDatabase,
        currentTable,
        routeView
      )
    }

    const fieldCheckViewId = fieldsRequireViewId ? viewId : null
    const fieldsLoadedFor = $store.getters['field/isLoadedFor'](
      currentTable.id,
      fieldCheckViewId
    )
    if (!fieldsLoadedFor) {
      await $store.dispatch('field/fetchAll', {
        table: currentTable,
        viewId: fieldCheckViewId,
      })
    }

    if (viewId !== null && viewId !== 0) {
      try {
        const { view } = await $store.dispatch('view/selectById', viewId)
        const viewType = $registry.get('view', view.type)
        result.view = view

        if (viewType.isDeactivated(currentDatabase.workspace.id)) {
          result.error = {
            statusCode: 400,
            message: viewType.getDeactivatedText(),
          }
          return result
        }

        const currentFields = $store.getters['field/getAll']
        await viewType.fetch(
          { store: $store, app: nuxtApp },
          currentDatabase,
          view,
          currentFields,
          'page/'
        )
      } catch (e) {
        if (e.response === undefined && !(e instanceof StoreItemLookupError))
          throw e
        result.error = normalizeError(e)
        return result
      }
    }

    return result
  }
)

// While a redirect to the default view is pending the fetch has technically
// finished, but the page is about to be rendered again for the view it redirects
// to. It must keep showing the skeleton, otherwise the header briefly renders as
// if the table has no views.
const loading = computed(() => fetching.value || !!data.value?.redirect)
const view = computed(() => data.value?.view)
const dataError = computed(() => data.value?.error)

// The default view can only be resolved once the views have been fetched, so the
// redirect to it happens after the page has rendered.
watch(
  data,
  (value) => {
    if (value?.redirect) {
      router.replace(value.redirect)
    }
  },
  { immediate: true }
)

useHead(() => ({
  title:
    (view.value?.name ? view.value.name + ' - ' : '') +
    (table.value?.name ?? ''),
}))

let realtimePage = null

function unsubscribeRealtime() {
  if (realtimePage !== null) {
    $realtime.unsubscribe(realtimePage.page, realtimePage.params)
    realtimePage = null
  }
}

/**
 * Which page is subscribed to depends on the view, so it can only be done once the
 * view has been fetched.
 */
function subscribeRealtime() {
  unsubscribeRealtime()

  if (!table.value?.id) {
    return
  }

  realtimePage = {
    page: 'table',
    params: { table_id: table.value.id },
  }

  if (view.value) {
    const viewOwnershipType = $registry.get(
      'viewOwnershipType',
      view.value.ownership_type
    )
    const { page, params } = viewOwnershipType.enhanceRealtimePagePayload(
      database.value,
      table.value,
      view.value,
      realtimePage
    )
    realtimePage.page = page
    realtimePage.params = params
  }

  $realtime.subscribe(realtimePage.page, realtimePage.params)
}

watch(
  [loading, view],
  () => {
    if (!loading.value && !data.value?.redirect) {
      subscribeRealtime()
    }
  },
  { immediate: true }
)

onBeforeUnmount(unsubscribeRealtime)

/**
 * When the user leaves to another page we want to unselect the selected table. This
 * way it will not be highlighted the left sidebar.
 */
onBeforeRouteLeave((to, from) => {
  $store.dispatch('view/unselect')
  $store.dispatch('table/unselect')
})

function selectedView(v) {
  if (view.value && view.value.id === v.id) return

  router.push({
    name: 'database-table',
    params: { viewId: v.id },
  })
}

async function navigateToRowModal(row) {
  const rowId = row?.id

  if (route.params.rowId !== undefined && route.params.rowId === rowId) {
    return
  }

  if (row) {
    // Prevent the row from being fetched again from the backend
    // when the route is updated.
    await $store.dispatch('rowModalNavigation/setRow', row)
  }

  await router.push({
    name: rowId ? 'database-table-row' : 'database-table',
    params: {
      databaseId: database.value.id,
      tableId: table.value.id,
      viewId: route.params.viewId,
      rowId,
    },
  })

  finishLoading()
}

async function setAdjacentRow(previous, row = null, term = null) {
  if (row) {
    await navigateToRowModal(row)
  } else {
    // If the row isn't provided then the row is
    // probably not visible to the user at the moment
    // and needs to be fetched
    await fetchAdjacentRow(previous, term)
  }
}

async function fetchAdjacentRow(previous, activeSearchTerm = null) {
  const { row, status } = await $store.dispatch(
    'rowModalNavigation/fetchAdjacentRow',
    {
      tableId: table.value.id,
      viewId: view.value?.id,
      activeSearchTerm,
      previous,
    }
  )

  if (status === 204 || status === 404) {
    const path = `table.adjacentRow.toast.notFound.${
      previous ? 'previous' : 'next'
    }`
    await $store.dispatch('toast/info', {
      title: $t(`${path}.title`),
      message: $t(`${path}.message`),
    })
  } else if (status !== 200) {
    await $store.dispatch('toast/error', {
      title: $t('table.adjacentRow.toast.error.title'),
      message: $t('table.adjacentRow.toast.error.message'),
    })
  }

  if (row) {
    await navigateToRowModal(row)
  }
}

const hasChildRoute = computed(() => route.matched.length > 1)
</script>
