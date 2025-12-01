<template>
  <div>
    <DefaultErrorPage v-if="error && !view" :error="error" />
    <Table
      v-else
      :database="database"
      :table="table"
      :fields="fields"
      :views="views"
      :view="view"
      :view-error="error"
      :table-loading="tableLoading"
      store-prefix="page/"
      @selected-view="selectedView"
      @selected-row="navigateToRowModal"
      @navigate-previous="
        (row, activeSearchTerm) => setAdjacentRow(true, row, activeSearchTerm)
      "
      @navigate-next="
        (row, activeSearchTerm) => setAdjacentRow(false, row, activeSearchTerm)
      "
    ></Table>
    <NuxtChild :database="database" :table="table" :fields="fields" />
  </div>
</template>

<script>
import { mapState } from 'vuex'

import Table from '@baserow/modules/database/components/table/Table'
import { StoreItemLookupError } from '@baserow/modules/core/errors'
import { getDefaultView } from '@baserow/modules/database/utils/view'
import DefaultErrorPage from '@baserow/modules/core/components/DefaultErrorPage'
import { normalizeError } from '@baserow/modules/database/utils/errors'

/**
 * This page component is the skeleton for a table. Depending on the selected view it
 * will load the correct components into the header and body.
 */
export default {
  components: { DefaultErrorPage, Table },
  /**
   * When the user leaves to another page we want to unselect the selected table. This
   * way it will not be highlighted the left sidebar.
   */
  beforeRouteLeave(to, from, next) {
    this.$store.dispatch('view/unselect')
    this.$store.dispatch('table/unselect')
    this.$store.dispatch('application/unselect')
    next()
  },
  /**
   * If a `rowId` is provided in the route params, we want to immediately open
   * the row modal in the table page and show the `database-table-row` URL in
   * the browser. This function parses the params and fetches the data needed to
   * render the page correctly, redirecting to the table page if the row is not
   * found. If the row is found in the store or in the backend, calling `next()`
   * will open the row modal and will update the URL in the browser correctly.
   */
  async beforeRouteUpdate(to, from, next) {
    function parseIntOrNull(x) {
      return x != null ? parseInt(x) : null
    }

    const currentRowId = parseIntOrNull(to.params?.rowId)
    const currentTableId = parseIntOrNull(to.params.tableId)

    const storeRow = this.$store.getters['rowModalNavigation/getRow']
    const prevTableId = parseIntOrNull(from.params.tableId)
    const failedToFetchTableRowId =
      this.$store.getters['rowModalNavigation/getFailedToFetchTableRowId']

    if (currentRowId == null) {
      // If the rowId is null, we want to close the row modal and show the table
      // page, so clear the store accordingly.
      await this.$store.dispatch('rowModalNavigation/clearRow')
    } else if (
      failedToFetchTableRowId &&
      parseIntOrNull(failedToFetchTableRowId?.rowId) === currentRowId &&
      parseIntOrNull(failedToFetchTableRowId?.tableId) === currentTableId
    ) {
      // Show the table page if the row failed to fetch.
      return next({
        name: 'database-table',
        params: {
          ...to.params,
          rowId: null,
        },
      })
    } else if (
      storeRow?.id !== currentRowId ||
      prevTableId !== currentTableId
    ) {
      // Fetch the row if it's not already in the store. If the row is not found,
      // the store will be updated with the failedToFetchTableRowId and the table
      // page will be shown.
      const row = await this.$store.dispatch('rowModalNavigation/fetchRow', {
        tableId: currentTableId,
        rowId: currentRowId,
      })
      if (row == null) {
        return next({
          name: 'database-table',
          params: {
            ...to.params,
            rowId: null,
          },
        })
      }
    }
    next()
  },
  layout: 'app',
  /**
   * Because there is no hook that is called before the route changes, we need the
   * tableLoading middleware to change the table loading state. This change will get
   * rendered right away. This allows us to have a custom loading animation when
   * switching views.
   */
  middleware: ['tableLoading'],
  /**
   * Prepares all the table, field and view data for the provided database, table and
   * view id.
   */
  async asyncData({ store, params, query, error, app, redirect, route }) {
    // @TODO figure out why the id's aren't converted to an int in the route.
    const databaseId = parseInt(params.databaseId)
    const tableId = parseInt(params.tableId)
    const viewId = params.viewId ? parseInt(params.viewId) : null
    // let's use undefined for view, as it's explicitly checked in components
    const data = { error: null, view: undefined, fields: null }
    // Try to find the table in the already fetched applications by the
    // workspacesAndApplications middleware and select that one. By selecting the table, the
    // fields and views are also going to be fetched.
    try {
      const { database, table, error } = await store.dispatch(
        'table/selectById',
        {
          databaseId,
          tableId,
        }
      )
      await store.dispatch('workspace/selectById', database.workspace.id)
      data.database = database
      data.table = table

      if (error) {
        data.error = normalizeError(error)
        return data
      }
    } catch (e) {
      // In case of a network error we want to fail hard.
      if (e.response === undefined && !(e instanceof StoreItemLookupError)) {
        throw e
      }
      data.database = null
      data.table = null
      data.error = normalizeError(e)
      return data
    }

    // After selecting the table the fields become available which need to be added to
    // the data.
    data.fields = store.getters['field/getAll']

    // Without a viewId, redirect the user to the default or the first available view.
    if (viewId === null) {
      const rowId = params.rowId ? parseInt(params.rowId) : null
      const workspaceId = data.database.workspace.id
      const viewToUse = getDefaultView(app, store, workspaceId, rowId !== null)

      if (viewToUse !== undefined) {
        params.viewId = viewToUse.id
        return redirect({
          name: route.name,
          params,
          query,
        })
      }
    }

    // If a view id is provided and the table is selected we can select the view. The
    // views that belong to the table have already been fetched so we just need to
    // select the correct one.
    if (viewId !== null && viewId !== 0) {
      try {
        const { view } = await store.dispatch('view/selectById', viewId)
        data.view = view

        // It might be possible that the view also has some stores that need to be
        // filled with initial data so we're going to call the fetch function here.
        const type = app.$registry.get('view', view.type)

        if (type.isDeactivated(data.database.workspace.id)) {
          return error({ statusCode: 400, message: type.getDeactivatedText() })
        }

        await type.fetch(
          { store, app },
          data.database,
          view,
          data.fields,
          'page/'
        )
      } catch (e) {
        // In case of a network error we want to fail hard.
        if (e.response === undefined && !(e instanceof StoreItemLookupError)) {
          throw e
        }
        data.error = normalizeError(e)

        return data
      }
    }
    if (params.rowId) {
      await store.dispatch('rowModalNavigation/fetchRow', {
        tableId,
        rowId: params.rowId,
        viewId: params.viewId,
      })
    }
    return data
  },
  data() {
    return {
      realtimePage: null,
    }
  },
  head() {
    return {
      title: (this.view ? this.view.name + ' - ' : '') + this.table?.name || '',
    }
  },
  computed: {
    ...mapState({
      // We need the tableLoading state to show a small loading animation when
      // switching between views. Because some of the data will be populated by
      // the asyncData function and some by mapping the state of a store it could look
      // a bit strange for the user when switching between views because not all data
      // renders at the same time. That is why we show this loading animation. Store
      // changes are always rendered right away.
      tableLoading: (state) => state.table.loading,
      views: (state) => state.view.items,
    }),
  },
  /**
   * The beforeCreate hook is called right after the asyncData finishes and when the
   * page has been rendered for the first time. The perfect moment to stop the table
   * loading animation.
   */
  beforeCreate() {
    this.$store.dispatch('table/setLoading', false)
  },
  mounted() {
    if (this.table) {
      const realtimePage = {
        page: 'table',
        params: { table_id: this.table.id },
      }
      if (this.view) {
        const viewOwnershipType = this.$registry.get(
          'viewOwnershipType',
          this.view.ownership_type
        )
        const { page, params } = viewOwnershipType.enhanceRealtimePagePayload(
          this.database,
          this.table,
          this.view,
          realtimePage
        )
        realtimePage.page = page
        realtimePage.params = params
      }
      this.realtimePage = realtimePage
      this.$realtime.subscribe(realtimePage.page, realtimePage.params)
    }
  },
  beforeDestroy() {
    if (this.table) {
      this.$realtime.unsubscribe(
        this.realtimePage.page,
        this.realtimePage.params
      )
      this.realtimePage = null
    }
  },
  methods: {
    selectedView(view) {
      if (this.view && this.view.id === view.id) {
        return
      }

      this.$router.push({
        name: 'database-table',
        params: {
          viewId: view.id,
        },
      })
    },
    async setAdjacentRow(previous, row = null, activeSearchTerm = null) {
      if (row) {
        await this.navigateToRowModal(row)
      } else {
        // If the row isn't provided then the row is
        // probably not visible to the user at the moment
        // and needs to be fetched
        await this.fetchAdjacentRow(previous, activeSearchTerm)
      }
    },
    async navigateToRowModal(row) {
      const rowId = row?.id
      if (
        this.$route.params.rowId !== undefined &&
        this.$route.params.rowId === rowId
      ) {
        return
      }

      if (row) {
        // Prevent the row from being fetched again from the backend
        // when the route is updated
        await this.$store.dispatch('rowModalNavigation/setRow', row)
      }

      const location = {
        name: rowId ? 'database-table-row' : 'database-table',
        params: {
          databaseId: this.database.id,
          tableId: this.table.id,
          viewId: this.$route.params.viewId,
          rowId,
        },
      }
      this.$router.push(location)
    },
    async fetchAdjacentRow(previous, activeSearchTerm = null) {
      const { row, status } = await this.$store.dispatch(
        'rowModalNavigation/fetchAdjacentRow',
        {
          tableId: this.table.id,
          viewId: this.view?.id,
          activeSearchTerm,
          previous,
        }
      )

      if (status === 204 || status === 404) {
        const translationPath = `table.adjacentRow.toast.notFound.${
          previous ? 'previous' : 'next'
        }`
        await this.$store.dispatch('toast/info', {
          title: this.$t(`${translationPath}.title`),
          message: this.$t(`${translationPath}.message`),
        })
      } else if (status !== 200) {
        await this.$store.dispatch('toast/error', {
          title: this.$t(`table.adjacentRow.toast.error.title`),
          message: this.$t(`table.adjacentRow.toast.error.message`),
        })
      }

      if (row) {
        await this.navigateToRowModal(row)
      }
    },
  },
}
</script>
