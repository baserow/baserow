<template>
  <Modal ref="modal" :tiny="true">
    <h2 class="box__title">
      {{ $t('deleteDataScanModal.title') }}
    </h2>
    <Error :error="error"></Error>
    <div>
      <p>
        {{ $t('deleteDataScanModal.confirmation') }}
      </p>
      <div class="actions">
        <div class="align-right">
          <Button
            type="danger"
            size="large"
            full-width
            :disabled="loading"
            :loading="loading"
            @click.prevent="doDelete"
          >
            {{ $t('deleteDataScanModal.delete') }}
          </Button>
        </div>
      </div>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import { DataScannerScansService } from '@baserow_enterprise/services/dataScanner'

export default {
  name: 'DeleteDataScanModal',
  mixins: [modal, error],
  props: {
    scan: {
      type: Object,
      required: true,
    },
  },
  emits: ['deleted'],
  data() {
    return {
      loading: false,
    }
  },
  methods: {
    async doDelete() {
      this.hideError()
      this.loading = true

      try {
        await DataScannerScansService(this.$client).delete(this.scan.id)
        this.$emit('deleted', this.scan.id)
        this.hide()
      } catch (error) {
        this.handleError(error)
      }

      this.loading = false
    },
  },
}
</script>
