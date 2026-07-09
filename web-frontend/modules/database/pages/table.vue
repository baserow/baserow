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
      v-if="hasChildRoute && ready"
      :database="database"
      :table="table"
      :fields="fields"
    />
  </div>
</template>

<script setup>
import {
  ref,
  computed,
  watch,
  onMounted,
  onBeforeUnmount,
  onServerPrefetch,
} from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { useHead } from '#imports'
import { navigateTo } from '#app'

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
    // Middleware specifically for the table. It selects the workspace, database
    // and table based on the provided route parameters, using store lookups only.
    // The views, fields and row are fetched by the page itself so that the
    // navigation isn't blocked.
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

const views = computed(() => $store.state.view.items)

const { data, ready, asyncData } = await usePageAsyncData(
  `database-table-page-${route.params.databaseId}-${route.params.tableId}-${route.params.viewId ?? 'null'}`,
  async () => {
    // Use current route params (not captured params) so refresh works correctly.
    const currentParams = { ...route.params }
    const routeName = route.name
    const viewId = currentParams.viewId ? parseInt(currentParams.viewId) : null
    const rowId = currentParams.rowId ? parseInt(currentParams.rowId) : null
    // It's okay to use the `table/getSelected` because the correct ones are selected
    // using the `modules/database/middleware/selectWorkspaceDatabaseTable.js`
    // middleware.
    const currentTable = $store.getters['table/getSelected']
    const currentDatabase = $store.getters['application/getSelected']

    // Because this handler doesn't block the navigation, the user can navigate to
    // another table or view while it's still running. In that case the remaining
    // store writing steps must be skipped because they would race with the handler
    // of the newly opened page.
    const stale = () =>
      route.params.tableId !== currentParams.tableId ||
      route.params.viewId !== currentParams.viewId

    // Fetch the views if they're not in the store yet. This was previously done in
    // the `selectWorkspaceDatabaseTable` middleware, but it's done here so that the
    // navigation isn't blocked while fetching.
    if ($store.state.view.tableId !== currentTable.id) {
      await $store.dispatch('view/fetchAll', currentTable)
      if (stale()) return { stale: true }
    }

    // If the viewId isn't provided, redirect to the default view of the table. The
    // `selectWorkspaceDatabaseTable` middleware already handles this if the views
    // were in the store before navigating.
    if (viewId === null) {
      const defaultView = getDefaultView(
        nuxtApp,
        $store,
        currentDatabase.workspace.id,
        rowId !== null
      )

      if (defaultView) {
        return {
          redirect: {
            name: routeName,
            params: { ...currentParams, viewId: defaultView.id },
            query: { ...route.query },
          },
        }
      }
    }

    // In some cases, the backend needs the view ID to scope which fields to list.
    // This can happen when a user does not have full access to a table for example.
    const preliminaryView = $store.getters['view/get'](viewId)
    let fieldsRequireViewId = false
    if (preliminaryView) {
      const ownershipType = $registry.get(
        'viewOwnershipType',
        preliminaryView.ownership_type
      )
      fieldsRequireViewId = ownershipType.fetchingFieldsRequiresViewId(
        currentDatabase,
        currentTable,
        preliminaryView
      )
    }
    const fieldCheckViewId = fieldsRequireViewId ? viewId : null
    if (!$store.getters['field/isLoadedFor'](currentTable.id, fieldCheckViewId)) {
      await $store.dispatch('field/fetchAll', {
        table: currentTable,
        viewId: fieldCheckViewId,
      })
      if (stale()) return { stale: true }
    }

    // Handle the enlarged row modal state by already fetching the row if it's
    // provided in the params.
    if (rowId) {
      const row = await $store.dispatch('rowModalNavigation/fetchRow', {
        tableId: currentTable.id,
        rowId,
        viewId,
      })

      // If the fetch failed, redirect to the table without rowId so that the table
      // is still visible.
      if (!row) {
        return {
          redirect: {
            name: 'database-table',
            params: { ...currentParams, rowId: '' },
            query: { ...route.query },
          },
        }
      }
      if (stale()) return { stale: true }
    } else {
      // If no rowId is provided, then we want to make 100% sure any old rows are
      // cleared. This could be the case when a row is open, but the user navigates
      // to a page without a selected row.
      await $store.dispatch('rowModalNavigation/clearRow')
    }

    const currentFields = $store.getters['field/getAll']

    const result = {
      view: undefined,
      database: currentDatabase,
      table: currentTable,
      fields: currentFields,
    }

    if (viewId !== null && viewId !== 0) {
      if (stale()) return { stale: true }
      try {
        const { view } = await $store.dispatch('view/selectById', viewId)
        const type = $registry.get('view', view.type)
        result.view = view

        if (type.isDeactivated(currentDatabase.workspace.id)) {
          result.error = { statusCode: 400, message: type.getDeactivatedText() }
          return result
        }

        await type.fetch(
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

// Handle redirects returned by the handler, for example to the default view or
// when the row in the params doesn't exist. The client-side watcher handles it
// after a client-side navigation, and the `onServerPrefetch` makes the server
// respond with a redirect on the first page load.
watch(
  data,
  (d) => {
    if (d?.redirect) {
      router.replace(d.redirect)
    }
  },
  { immediate: true }
)

if (import.meta.server) {
  onServerPrefetch(async () => {
    await asyncData
    if (data.value?.redirect) {
      await nuxtApp.runWithContext(() =>
        navigateTo(data.value.redirect, { replace: true })
      )
    }
  })
}

// The table is rendered in a loading state until the async data is ready and the
// page is mounted. The mounted check keeps the server-rendered output limited to
// the loading header, exactly like before, so that hydration matches.
const mounted = ref(false)
const tableLoading = computed(
  () =>
    !mounted.value ||
    !ready.value ||
    data.value?.redirect !== undefined ||
    data.value?.stale === true
)

// Expose the actual values via computed shortcuts to make sure that if the asyncData
// recomputes, it will show the correct values. The database and table fall back to
// the ones selected by the middleware, so that the `Table` component always has its
// required props while the async data is loading.
const database = computed(
  () => data.value?.database ?? $store.getters['application/getSelected']
)
const table = computed(
  () => data.value?.table ?? $store.getters['table/getSelected']
)
const view = computed(() => data.value?.view)
const fields = computed(() => data.value?.fields ?? [])
const dataError = computed(() => data.value?.error)
let realtimePage = null

useHead(() => ({
  title:
    (view.value?.name ? view.value.name + ' - ' : '') +
    (table.value?.name ?? ''),
}))

onMounted(() => {
  mounted.value = true
})

/**
 * Subscribe to the realtime updates of the table as soon as the async data is
 * ready. This can't happen in the onMounted hook because the page is mounted
 * before the async data has been fetched on client-side navigation.
 */
watch(
  ready,
  (isReady) => {
    if (
      isReady &&
      realtimePage === null &&
      table.value &&
      !data.value?.redirect &&
      !data.value?.stale
    ) {
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
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  if (realtimePage !== null) {
    $realtime.unsubscribe(realtimePage.page, realtimePage.params)
    realtimePage = null
  }
})

/**
 * When only the rowId param changes, the page component is reused and the async
 * data doesn't refetch because its key doesn't include the rowId. Fetching or
 * clearing the row was previously done by a middleware on every route change,
 * but that's now handled here without blocking the navigation.
 */
watch(
  () => route.params.rowId,
  async (newRowId, oldRowId) => {
    if (!ready.value || newRowId === oldRowId) {
      return
    }
    const rowId = newRowId ? parseInt(newRowId) : null
    if (rowId) {
      const row = await $store.dispatch('rowModalNavigation/fetchRow', {
        tableId: table.value.id,
        rowId,
        viewId: view.value?.id ?? null,
      })
      if (!row) {
        router.replace({
          name: 'database-table',
          params: { ...route.params, rowId: '' },
          query: { ...route.query },
        })
      }
    } else {
      await $store.dispatch('rowModalNavigation/clearRow')
    }
  }
)

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
