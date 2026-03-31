<template>
  <div class="flex justify-content-end">
    <template v-if="resolved">
      <span class="color-success">
        <i class="iconoir-check"></i>
        {{ $t('dataScanner.resultResolved') }}
      </span>
    </template>
    <template v-else>
      <Button
        tag="a"
        size="tiny"
        type="secondary"
        :loading="loading"
        @click.prevent="resolve"
        >{{ $t('dataScanner.resolveResult') }}</Button
      >
    </template>
  </div>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import { DataScannerResultsService } from '@baserow_enterprise/services/dataScanner'

export default {
  name: 'DataScanResolveField',
  props: {
    row: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
      resolved: false,
    }
  },
  methods: {
    async resolve() {
      if (this.loading || this.resolved) return

      this.loading = true
      try {
        await DataScannerResultsService(this.$client).deleteResult(this.row.id)
        this.resolved = true
      } catch (error) {
        notifyIf(error)
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
