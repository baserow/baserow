<template>
  <PaginatedDropdown
    v-if="isDropdown"
    :fetch-page="fetchPage"
    :value="filter.value"
    :fetch-on-open="true"
    :disabled="disabled"
    :fixed-items="true"
    class="filters__value-dropdown"
    @input="$emit('input', $event)"
  ></PaginatedDropdown>
  <a
    v-else
    class="filters__value-link-row"
    :class="{
      'filters__value-link-row--disabled': disabled,
      'filters__value-link-row--loading': loading,
    }"
    @click.prevent="!disabled && $refs.selectModal.show()"
  >
    <template v-if="!loading">
      <template v-if="valid">
        {{
          name || $t('viewFilterTypeLinkRow.unnamed', { value: filter.value })
        }}
      </template>
      <div v-else class="filters__value-link-row-choose">
        {{ $t('viewFilterTypeLinkRow.choose') }}
      </div>
    </template>
    <SelectRowModal
      v-if="!disabled"
      ref="selectModal"
      :table-id="field.link_row_table_id"
      :view-id="field.link_row_limit_selection_view_id"
      :persistent-field-options-key="getPersistentFieldOptionsKey(field.id)"
      @selected="setValue"
    ></SelectRowModal>
  </a>
</template>

<script>
import { isInteger } from '@baserow/modules/core/utils/string'
import { getPersistentFieldOptionsKey } from '@baserow/modules/database/utils/field'
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import SelectRowModal from '@baserow/modules/database/components/row/SelectRowModal'
import viewFilter from '@baserow/modules/database/mixins/viewFilter'
import ViewService from '@baserow/modules/database/services/view'
import RowService from '@baserow/modules/database/services/row'

export default {
  name: 'ViewFilterTypeLinkRow',
  components: { PaginatedDropdown, SelectRowModal },
  mixins: [viewFilter],
  data() {
    return {
      name: '',
      rowInfo: null,
      loading: false,
    }
  },
  computed: {
    valid() {
      return isInteger(this.filter.value)
    },
    isDropdown() {
      return this.readOnly && this.view && this.isPublicView
    },
  },
  watch: {
    'filter.value'() {
      this.setName()
    },
  },
  mounted() {
    this.setName()
  },
  methods: {
    getPersistentFieldOptionsKey(fieldId) {
      return getPersistentFieldOptionsKey(fieldId)
    },
    async setName() {
      const { value, preload_values: { display_name: displayName } = {} } =
        this.filter

      if (!value) {
        this.name = ''
      } else if (displayName) {
        // set the name from preload_values
        this.name = displayName
      } else if (this.rowInfo) {
        // Set the name from previous row info
        const { row, primary } = this.rowInfo
        this.name = this.$registry
          .get('field', primary.type)
          .toHumanReadableString(primary, row[`field_${primary.id}`])
        this.rowInfo = null
      } else if (!this.isDropdown) {
        // Get the name from server
        this.loading = true
        try {
          this.name = await RowService(this.$client).getName(
            this.field.link_row_table_id,
            value
          )
        } finally {
          this.loading = false
        }
      }
    },
    setValue({ row, primary }) {
      this.rowInfo = { row, primary }
      this.$emit('input', row.id.toString())
    },
    fetchPage(page, search) {
      const publicAuthToken =
        this.$store.getters['page/view/public/getAuthToken']
      return ViewService(this.$client).linkRowFieldLookup(
        this.view.id,
        this.field.id,
        page,
        search,
        100,
        publicAuthToken
      )
    },
  },
}
</script>
