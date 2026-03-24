<template>
  <Context ref="context" overflow-scroll max-height-if-outside-viewport>
    <template v-if="scan && scan.id">
      <ul class="context__menu">
        <li class="context__menu-item">
          <a
            class="context__menu-item-link"
            :class="{
              'context__menu-item-link--loading': triggerLoading,
              'context__menu-item-link--disabled': scan.is_running,
              disabled: scan.is_running,
            }"
            @click.prevent="!scan.is_running && triggerScan()"
          >
            <i class="context__menu-item-icon iconoir-play"></i>
            {{ $t('dataScanner.runNow') }}
          </a>
        </li>
        <li class="context__menu-item">
          <a
            class="context__menu-item-link"
            :class="{
              disabled: scan.is_running,
            }"
            @click.prevent="!scan.is_running && handleEdit()"
          >
            <i class="context__menu-item-icon iconoir-edit-pencil"></i>
            {{ $t('dataScanner.edit') }}
          </a>
        </li>
        <li class="context__menu-item">
          <a class="context__menu-item-link" @click.prevent="handleViewResults">
            <i class="context__menu-item-icon iconoir-list"></i>
            {{ $t('dataScanner.viewResults') }}
          </a>
        </li>
        <li class="context__menu-item context__menu-item--with-separator">
          <a
            class="context__menu-item-link context__menu-item-link--delete"
            :class="{
              disabled: scan.is_running,
            }"
            @click.prevent="!scan.is_running && showDeleteModal()"
          >
            <i class="context__menu-item-icon iconoir-bin"></i>
            {{ $t('dataScanner.delete') }}
          </a>
        </li>
      </ul>
      <DeleteDataScanModal
        ref="deleteDataScanModal"
        :scan="scan"
        @deleted="onDeleted"
      />
    </template>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { DataScannerScansService } from '@baserow_enterprise/services/dataScanner'
import DeleteDataScanModal from '@baserow_enterprise/components/admin/dataScanner/DeleteDataScanModal'

export default {
  name: 'DataScanActionsField',
  components: { DeleteDataScanModal },
  mixins: [context],
  emits: ['edit', 'deleted', 'triggered', 'view-results'],
  props: {
    scan: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      triggerLoading: false,
    }
  },
  methods: {
    handleEdit() {
      this.$emit('edit', this.scan)
      this.hide()
    },
    handleViewResults() {
      this.$emit('view-results', this.scan)
      this.hide()
    },
    showDeleteModal() {
      if (this.scan.is_running) return

      this.hide()
      this.$refs.deleteDataScanModal.show()
    },
    onDeleted(scanId) {
      this.$emit('deleted', scanId)
    },
    async triggerScan() {
      if (this.triggerLoading || this.scan.is_running) return

      this.triggerLoading = true
      try {
        const { data } = await DataScannerScansService(this.$client).trigger(
          this.scan.id
        )
        this.$emit('triggered', data)
        this.hide()
      } catch (error) {
        notifyIf(error)
      } finally {
        this.triggerLoading = false
      }
    },
  },
}
</script>
