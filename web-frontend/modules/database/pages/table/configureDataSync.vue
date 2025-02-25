<template>
  <div>
    <ConfigureDataSyncModal
      ref="configureDataSyncModal"
      :database="database"
      :table="table"
      @hidden="back"
    ></ConfigureDataSyncModal>
  </div>
</template>

<script>
import ConfigureDataSyncModal from '@baserow/modules/database/components/dataSync/ConfigureDataSyncModal'

export default {
  components: { ConfigureDataSyncModal },
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
    if (this.table.data_sync === null) {
      return this.back()
    }

    this.$nextTick(() => {
      this.$refs.configureDataSyncModal.show(
        this.$route.params.selectedPage || undefined
      )
    })
  },
  methods: {
    back() {
      delete this.$route.params.selectedPage
      this.$router.push({ name: 'database-table', params: this.$route.params })
    },
  },
}
</script>
