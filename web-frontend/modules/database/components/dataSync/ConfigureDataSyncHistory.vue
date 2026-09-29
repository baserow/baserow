<template>
  <div>
    <h2 class="box__title">{{ $t('dataSyncRuns.title') }}</h2>
    <p class="margin-bottom-2">{{ $t('dataSyncRuns.description') }}</p>
    <DataSyncRunsList :data-sync-id="table.data_sync.id" />
  </div>
</template>

<script>
import DataSyncRunsList from '@baserow/modules/database/components/dataSync/DataSyncRunsList'

export default {
  name: 'ConfigureDataSyncHistory',
  components: { DataSyncRunsList },
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
  },
}
</script>
