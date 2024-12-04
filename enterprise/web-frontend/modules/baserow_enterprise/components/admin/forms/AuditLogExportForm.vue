<template>
  <form @submit.prevent="submit">
    <TableCSVExporter :loading="loading"></TableCSVExporter>
    <slot></slot>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import TableCSVExporter from '@baserow/modules/database/components/export/TableCSVExporter'

export default {
  name: 'AuditLogExportForm',
  components: { TableCSVExporter },
  mixins: [form],
  props: {
    loading: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      values: {},
    }
  },
}
</script>
