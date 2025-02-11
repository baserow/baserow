<template>
  <div>
    <WebhookModal
      ref="webhookModal"
      :database="database"
      :table="table"
      :fields="fields"
      @hidden="$router.push({ name: 'database-table', params: $route.params })"
    />
  </div>
</template>
<script>
import WebhookModal from '@baserow/modules/database/components/webhook/WebhookModal'

export default {
  components: { WebhookModal },
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
  },
  mounted() {
    this.$nextTick(() => {
      this.$refs.webhookModal.show()
    })
  },
}
</script>
