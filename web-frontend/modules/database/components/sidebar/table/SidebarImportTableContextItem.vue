<template>
  <a
    class="context__menu-item-link"
    :class="{
      'context__menu-item-link--loading': loading,
      disabled: disabled || loading,
    }"
    @click="importFile()"
  >
    <i class="context__menu-item-icon iconoir-import"></i>
    {{ $t('sidebarItem.importFile') }}
    <ImportFileModal
      ref="importFileModal"
      :database="database"
      :table="table"
      :fields="fields"
    />
  </a>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import FieldService from '@baserow/modules/database/services/field'
import { populateField } from '@baserow/modules/database/store/field'
import ImportFileModal from '@baserow/modules/database/components/table/ImportFileModal'

export default {
  name: 'SidebarImportTableContextItem',
  components: { ImportFileModal },
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['click'],
  data() {
    return {
      loading: false,
      fields: [],
    }
  },
  methods: {
    // Sidebar has no fields in the store, so fetch them before opening. The
    // modal reads `field._.type`, so the raw fields must be populated first.
    async importFile() {
      if (this.loading || this.disabled) {
        return
      }
      this.loading = true
      try {
        const { data } = await FieldService(this.$client).fetchAll(
          this.table.id
        )
        this.fields = data.map((field) => populateField(field, this.$registry))
        this.$emit('click')
        this.$refs.importFileModal.show()
      } catch (error) {
        notifyIf(error, 'table')
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
