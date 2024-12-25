<template>
  <Table
    :database="database"
    :table="table"
    :fields="fields"
    :views="views"
    :view="view"
    :table-loading="tableLoading"
    :read-only="true"
    :disable-filter="true"
    :disable-sort="true"
    :disable-group-by="true"
    store-prefix="template/"
    @selected-view="selectView({ viewId: $event.id })"
  ></Table>
</template>

<script>
import Table from '@baserow/modules/database/components/table/Table'

import FieldService from '@baserow/modules/database/services/field'
import { populateField } from '@baserow/modules/database/store/field'
import ViewService from '@baserow/modules/database/services/view'
import { populateView } from '@baserow/modules/database/store/view'
import { Mutex } from 'async-mutex'

export default {
  name: 'TableTemplate',
  components: { Table },
  props: {
    pageValue: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      database: {},
      table: {},
      fields: [],
      views: [],
      view: {},
      tableLoading: true,
      mutex: new Mutex(),
    }
  },
  watch: {
    pageValue(value) {
      this.fetchTable(value.database, value.table)
    },
  },
  mounted() {
    this.fetchTable(this.pageValue.database, this.pageValue.table)
  },
  methods: {
    async runExclusiveUnlessAlreadyLocked({ callback, alreadyLocked = false }) {
      if (alreadyLocked) {
        return await callback()
      } else {
        return await this.mutex.runExclusive(callback)
      }
    },
    /**
     * Fetches and prepares all the table, field and view data for the provided
     * database and table.
     */
    async fetchTable(database, table) {
      await this.runExclusiveUnlessAlreadyLocked({
        callback: async () => {
          // If the new table is already selected, then we don't need to do anything.
          if (table.id === this.table.id) {
            return
          }

          this.tableLoading = true
          this.database = database
          this.table = table

          // Fetch and prepare the fields of the given table. The primary field is
          // extracted from the array and moved to a separate object because that is what
          // the `Table` components expects.
          const { data: fieldsData } = await FieldService(
            this.$client
          ).fetchAll(table.id)
          fieldsData.forEach((part, index, d) => {
            populateField(fieldsData[index], this.$registry)
          })
          this.fields = fieldsData

          // Fetch and prepare the views of the given table.
          const { data: viewsData } = await ViewService(this.$client).fetchAll(
            table.id,
            true,
            true,
            true,
            true
          )
          viewsData.forEach((part, index, d) => {
            populateView(viewsData[index], this.$registry)
          })
          this.views = viewsData

          // After selecting the table, the user expects to see the table data and that is
          // only possible if a view is selected. By calling the `selectView` method
          // without parameters, the first view is selected.
          await this.selectView({ alreadyLocked: true })
        },
      })
    },
    /**
     * Selects the view with the given `viewId`. If no `viewId` is provided, then the
     * first view will be selected.
     */
    async selectView({ viewId = null, alreadyLocked = false }) {
      // If the new view is already selected, we don't need to do anything.
      if (viewId === this.view.id) {
        return
      }

      await this.runExclusiveUnlessAlreadyLocked({
        alreadyLocked,
        callback: async () => {
          // If the new view is already selected, we don't need to do anything.
          if (viewId === this.view.id) {
            return
          }

          this.tableLoading = true

          // If no viewId is provided, we want to select the first the first view.
          const firstView = this.views.length > 0 ? this.views[0] : null
          if (viewId === null && firstView !== null) {
            viewId = firstView.id
          }

          // Update the selected state in all the views.
          this.views.forEach((view) => {
            view._.selected = view.id === viewId
          })

          const view = this.views.find((item) => item.id === viewId)
          this.view = view

          // It might be possible that the view also has some stores that need to be
          // filled with initial data, so we're going to call the fetch function here.
          const type = this.$registry.get('view', view.type)
          await type.fetch(
            { store: this.$store, app: this },
            this.database,
            view,
            this.fields,
            'template/'
          )
          this.tableLoading = false
        },
      })
    },
  },
}
</script>
