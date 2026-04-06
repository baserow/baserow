<template>
  <Modal ref="modal" @hidden="hideError">
    <h2 class="box__title">
      {{ isEdit ? $t('dataScanner.editScan') : $t('dataScanner.createScan') }}
    </h2>
    <Error v-if="error.visible" :error="error" />
    <DataScanForm
      ref="form"
      :default-values="formDefaults"
      @submitted="handleSubmit"
    >
      <div class="actions">
        <div class="align-right">
          <Button
            type="primary"
            size="large"
            :loading="submitLoading"
            :disabled="submitLoading"
            @click="$refs.form.submit()"
          >
            {{ isEdit ? $t('action.save') : $t('action.create') }}
          </Button>
        </div>
      </div>
    </DataScanForm>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { DataScannerScansService } from '@baserow_enterprise/services/dataScanner'
import DataScanForm from '@baserow_enterprise/components/admin/dataScanner/DataScanForm'

export default {
  name: 'DataScanModal',
  components: { DataScanForm },
  mixins: [modal, error],
  emits: ['saved'],
  props: {
    scan: {
      type: Object,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      submitLoading: false,
    }
  },
  computed: {
    isEdit() {
      return this.scan && this.scan.id
    },
    formDefaults() {
      if (this.isEdit) {
        return {
          name: this.scan.name,
          scan_type: this.scan.scan_type,
          pattern: this.scan.pattern || '',
          frequency: this.scan.frequency,
          scan_all_workspaces: this.scan.scan_all_workspaces,
          whole_words: this.scan.whole_words ?? true,
          workspace_ids: this.scan.workspace_ids || [],
          list_items: this.scan.list_items || [],
          source_workspace_id: this.scan.source_workspace_id || null,
          source_database_id: this.scan.source_database_id || null,
          source_table_id: this.scan.source_table_id || null,
          source_field_id: this.scan.source_field_id || null,
        }
      }
      return {}
    },
  },
  methods: {
    async handleSubmit(values) {
      this.hideError()
      this.submitLoading = true

      try {
        let data
        if (this.isEdit) {
          const response = await DataScannerScansService(this.$client).update(
            this.scan.id,
            values
          )
          data = response.data
        } else {
          const response = await DataScannerScansService(this.$client).create(
            values
          )
          data = response.data
        }
        this.$emit('saved', data)
        this.hide()
      } catch (error) {
        this.handleError(error)
        notifyIf(error)
      } finally {
        this.submitLoading = false
      }
    },
  },
}
</script>
