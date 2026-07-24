<template>
  <div v-if="row[column.key]" :title="`${row[column.key]} (${id})`">
    <nuxt-link v-if="linkTo" class="data-table__cell-link" :to="linkTo">
      {{ row[column.key] }}
      <span class="color-neutral">({{ id }})</span>
    </nuxt-link>
    <template v-else>
      {{ row[column.key] }}
      <span class="color-neutral">({{ id }})</span>
    </template>
  </div>
  <div v-else>-</div>
</template>

<script>
export default {
  name: 'NameWithIdField',
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
    id() {
      return this.row[this.column.additionalProps.idKey]
    },
    linkTo() {
      const routeName = this.column.additionalProps.navigateRoute
      if (!routeName) {
        return null
      }
      return { name: routeName, query: { search: String(this.id) } }
    },
  },
}
</script>
