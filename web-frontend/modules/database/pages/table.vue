<template>
  <div v-if="database && table">
    <DefaultErrorPage v-if="dataError && !view" :error="dataError" />

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
import { computed, onMounted, onBeforeUnmount, watch } from 'vue'
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

const tableLoading = computed(() => $store.state.table.loading)
const views = computed(() => $store.state.view.items)

function parseIntOrNull(x) {
  return x != null ? parseInt(x) : null
}

// Database and table is selected by the middleware
const database = computed(() => $store.getters['application/getSelected'])
const table = computed(() => $store.getters['table/getSelected'])

const { data, error, pending, status, refresh } = await useAsyncData(
  `database-table-page-${route.params.viewId ?? 'null'}`,
  async () => {
    // Use current route params (not captured params) so refresh works correctly
    const currentParams = route.params
    const viewId = currentParams.viewId ? parseInt(currentParams.viewId) : null

    const result = {
      view: undefined,
    }

    const currentTable = $store.getters['table/getSelected']
    const currentDatabase = $store.getters['application/getSelected']

    await $store.dispatch('view/fetchAll', currentTable)

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

    $store.dispatch('table/setLoading', false)

    return result
  }
)

// Watch for route changes and refresh data
watch(
  () => [route.params.tableId, route.params.viewId],
  async ([newTableId, newViewId], [oldTableId, oldViewId]) => {
    if (newTableId && (newTableId !== oldTableId || newViewId !== oldViewId)) {
      // Set loading state immediately to hide old content before refresh
      $store.dispatch('table/setLoading', true)
      await refresh()
    }
  }
)

if (error.value) {
  // If we have an error we want to display it.
  throw error.value
}

if (data.value?.redirect) {
  // We have a redirect, we can apply it now
  await navigateTo(data.value.redirect.href)
}

/**
 * Expose the actual values via computed shortcuts
 */

const view = computed(() => data.value?.view || {})
const fields = computed(() => $store.getters['field/getAll'])
const dataError = computed(() => data.value?.error)

/**
 * Set page <head> title
 */
useHead(() => ({
  title:
    (view.value ? view.value.name + ' - ' : '') + (table.value?.name ?? ''),
}))

/**
 * Lifecycle
 */
onMounted(() => {
  if (table.value) {
    $realtime.subscribe('table', { table_id: table.value.id })
  }
})

onBeforeUnmount(() => {
  if (table.value) {
    $realtime.unsubscribe('table', { table_id: table.value.id })
  }
})

/**
 * beforeRouteLeave()
 *
 * Unselect when leaving page.
 */
onBeforeRouteLeave((_to, _from) => {
  $store.dispatch('view/unselect')
  $store.dispatch('table/unselect')
  $store.dispatch('application/unselect')
})

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

  if (currentRowId == null) {
    await $store.dispatch('rowModalNavigation/clearRow')
  } else if (
    failed &&
    parseIntOrNull(failed?.rowId) === currentRowId &&
    parseIntOrNull(failed?.tableId) === currentTableId
  ) {
    return next({
      name: 'database-table',
      params: { ...to.params, rowId: null },
    })
  } else if (storeRow?.id !== currentRowId || prevTableId !== currentTableId) {
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
