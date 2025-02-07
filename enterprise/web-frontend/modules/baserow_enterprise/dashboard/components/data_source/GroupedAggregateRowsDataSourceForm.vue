<template><div></div></template>

<script>
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'GroupedAggregateRowsDataSourceForm',
  mixins: [form],
  props: {
    dashboard: {
      type: Object,
      required: true,
    },
    widget: {
      type: Object,
      required: true,
    },
    dataSource: {
      type: Object,
      required: true,
    },
    storePrefix: {
      type: String,
      required: false,
      default: '',
    },
  },
}
</script>
