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
      :table-loading="tableLoading"
      store-prefix="page/"
      @selected-view="selectedView"
      @selected-row="navigateToRowModal"
      @navigate-previous="(row, term) => setAdjacentRow(true, row, term)"
      @navigate-next="(row, term) => setAdjacentRow(false, row, term)"
    />
    <NuxtPage
      v-if="hasChildRoute"
      :database="database"
      :table="table"
      :fields="fields"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, watch, ref } from 'vue'
import {
  onBeforeRouteLeave,
  onBeforeRouteUpdate,
  useRoute,
  useRouter,
} from 'vue-router'
import { useHead } from '#imports'
import { useAsyncData } from '#app'

import Table from '@baserow/modules/database/components/table/Table'
import DefaultErrorPage from '@baserow/modules/core/components/DefaultErrorPage'
import { StoreItemLookupError } from '@baserow/modules/core/errors'
import { getDefaultView } from '@baserow/modules/database/utils/view'
import { normalizeError } from '@baserow/modules/database/utils/errors'

definePageMeta({
  name: 'database-table',
  layout: 'app',
  middleware: [
    'settings',
    'authenticated',
    'workspacesAndApplications',
     // Because there is no hook that is called before the route changes, we need the
     // tableLoading middleware to change the table loading state. This change will get
     // rendered right away. This allows us to have a custom loading animation when
     // switching views.
    'tableLoading',
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

// We need the tableLoading state to show a small loading animation when
// switching between views. Because some of the data will be populated by
// the asyncData function and some by mapping the state of a store it could look
// a bit strange for the user when switching between views because not all data
// renders at the same time. That is why we show this loading animation. Store
// changes are always rendered right away.
const tableLoading = computed(() => $store.state.table.loading)
const views = computed(() => $store.state.view.items)

function parseIntOrNull(x) {
  return x != null ? parseInt(x) : null
}

const { data, error, pending, status, refresh } = await useAsyncData(
  `database-table-page-${route.params.databaseId}-${route.params.tableId}-${route.params.viewId ?? 'null'}`,
  async () => {
    // Use current route params (not captured params) so refresh works correctly
    const currentParams = { ...route.params }
    const viewId = currentParams.viewId ? parseInt(currentParams.viewId) : null
    // It's okay to use the `table/getSelected` because the correct ones are selected
    // using the `modules/database/middleware/selectWorkspaceDatabaseTable.js`
    // middleware.
    const currentTable = $store.getters['table/getSelected']
    const currentDatabase = $store.getters['application/getSelected']

    const result = {
      view: undefined,
      database: currentDatabase,
      table: currentTable,
    }

    if ($store.state.view.tableId !== currentTable.id) {
      await $store.dispatch('view/fetchAll', currentTable)
    }

    // No viewId → redirect to default view
    if (viewId === null) {
      const rowId = currentParams.rowId ? parseInt(currentParams.rowId) : null
      const workspaceId = currentDatabase.workspace.id
      const viewToUse = getDefaultView(
        nuxtApp,
        $store,
        workspaceId,
        rowId !== null
      )

      if (viewToUse) {
        const newParams = { ...currentParams, viewId: viewToUse.id }
        // Let's redirect to the route WITH the viewId
        return {
          redirect: router.resolve({
            name: route.name,
            params: newParams,
            query: route.query,
          }),
        }
      }
    }

    // Fetch the Fields
    await $store.dispatch('field/fetchAll', currentTable)
    const fetchedFields = $store.getters['field/getAll']
    result.fields = fetchedFields

    // Select view
    if (viewId !== null && viewId !== 0) {
      try {
        const { view } = await $store.dispatch('view/selectById', viewId)

        result.view = view
        const type = $registry.get('view', view.type)

        if (type.isDeactivated(currentDatabase.workspace.id)) {
          result.error = { statusCode: 400, message: type.getDeactivatedText() }
          return result
        }

        await type.fetch(
          { store: $store, app: nuxtApp },
          currentDatabase,
          view,
          fetchedFields,
          'page/'
        )
      } catch (e) {
        if (e.response === undefined && !(e instanceof StoreItemLookupError))
          throw e
        result.error = normalizeError(e)
        return result
      }
    }

    // Possibly fetch selected row
    if (currentParams.rowId) {
      await $store.dispatch('rowModalNavigation/fetchRow', {
        tableId: currentTable.id,
        rowId: currentParams.rowId,
      })
    }

    return result
  }
)

if (error.value) {
  // If we have an error we want to display it.
  throw error.value
}

if (data.value?.redirect) {
  // We have a redirect, we can apply it now. Using `replace` so the intermediate
  // URL (without viewId) doesn't stay in the browser history — otherwise the back
  // button would land on it and immediately redirect forward again.
  await navigateTo(data.value.redirect.href, { replace: true })
}

/**
 * Expose the actual values via computed shortcuts
 */
const database = computed(() => data.value?.database)
const table = computed(() => data.value?.table)
const view = computed(() => data.value?.view)
const fields = computed(() => data.value?.fields)
const dataError = computed(() => data.value?.error)

/**
 * Set page <head> title
 */
useHead(() => ({
  title:
    (view.value?.name ? view.value.name + ' - ' : '') +
    (table.value?.name ?? ''),
}))

/**
 * The beforeCreate hook is called right after the asyncData finishes and when the
 * page has been rendered for the first time. The perfect moment to stop the table
 * loading animation.
 */
onMounted(() => {
  if (table.value) {
    $realtime.subscribe('table', { table_id: table.value.id })
  }
  $store.dispatch('table/setLoading', false)
})

onBeforeUnmount(() => {
  if (table.value) {
    $realtime.unsubscribe('table', { table_id: table.value.id })
  }
})

/**
 * When the user leaves to another page we want to unselect the selected table. This
 * way it will not be highlighted the left sidebar.
 */
onBeforeRouteLeave((to, from) => {
  $store.dispatch('view/unselect')
  $store.dispatch('table/unselect')
})

/**
 * If a `rowId` is provided in the route params, we want to immediately open
 * the row modal in the table page and show the `database-table-row` URL in
 * the browser. This function parses the params and fetches the data needed to
 * render the page correctly, redirecting to the table page if the row is not
 * found. If the row is found in the store or in the backend, calling `next()`
 * will open the row modal and will update the URL in the browser correctly.
 */
onBeforeRouteUpdate(async (to, from, next) => {
  const currentRowId = parseIntOrNull(to.params?.rowId)
  const currentTableId = parseIntOrNull(to.params.tableId)

  const storeRow = $store.getters['rowModalNavigation/getRow']
  const prevTableId = parseIntOrNull(from.params.tableId)
  const failed = $store.getters['rowModalNavigation/getFailedToFetchTableRowId']

  const isRowOnlyNavigation =
    currentTableId === prevTableId &&
    to.params.viewId === from.params.viewId &&
    to.params.rowId !== from.params.rowId

  console.log('route update', from, to)

  if (currentRowId == null) {
    // If the rowId is null, we want to close the row modal and show the table
    // page, so clear the store accordingly.
    await $store.dispatch('rowModalNavigation/clearRow')
  } else if (
    failed &&
    parseIntOrNull(failed?.rowId) === currentRowId &&
    parseIntOrNull(failed?.tableId) === currentTableId
  ) {
    // Show the table page if the row failed to fetch.
    return next({
      name: 'database-table',
      params: { ...to.params, rowId: null },
    })
  } else if (storeRow?.id !== currentRowId || prevTableId !== currentTableId) {
    // Fetch the row if it's not already in the store. If the row is not found,
    // the store will be updated with the failedToFetchTableRowId and the table
    // page will be shown.
    const row = await $store.dispatch('rowModalNavigation/fetchRow', {
      tableId: currentTableId,
      rowId: currentRowId,
    })
    if (row == null) {
      return next({
        name: 'database-table',
        params: { ...to.params, rowId: null },
      })
    }
  }
  next()

  if (isRowOnlyNavigation) {
    finishLoading()
  }
})

/**
 * Methods
 */
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
    // when the route is updated
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
