<template>
  <div>
    <nuxt-link v-if="hasAccess" :to="rowRoute" target="blank">
      {{ row.row_id }}
    </nuxt-link>
    <span v-else>{{ row.row_id }}</span>
  </div>
</template>

<script>
export default {
  name: 'DataScanRowLinkField',
  props: {
    row: {
      required: true,
      type: Object,
    },
    column: {
      required: true,
      type: Object,
    },
  },
  computed: {
    hasAccess() {
      const database = this.$store.getters['application/get'](
        this.row.database_id
      )
      if (!database || !database.tables) {
        return false
      }
      return database.tables.some((t) => t.id === this.row.table_id)
    },
    rowRoute() {
      return {
        name: 'database-table-row',
        params: {
          databaseId: this.row.database_id,
          tableId: this.row.table_id,
          viewId: '',
          rowId: this.row.row_id,
        },
      }
    },
  },
}
</script>
