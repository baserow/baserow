<template>
  <BaserowTable
    :fields="fields"
    :rows="rows"
    class="ab-table"
    :orientation="orientation"
  >
    <template #field-name="{ field }">
      <th :key="field.__id__" class="ab-table__header-cell">
        <slot name="field-name" :field="field">{{ field.name }}</slot>
      </th>
    </template>
    <template #cell-content="{ rowIndex, value, field, row }">
      <slot
        name="cell-content"
        :value="value"
        :field="field"
        :row-index="rowIndex"
        :row="row"
      >
        <td :key="field.id" class="ab-table__cell">
          <div class="ab-table__cell-content">
            {{ row[field.__id__] }}
          </div>
        </td>
      </slot>
    </template>
    <template #empty-state>
      <div class="ab-table__empty-state">
        <template v-if="contentLoading">
          <div class="loading-spinner" />
        </template>
        <template v-else>
          {{ $t('abTable.empty') }}
        </template>
      </div>
    </template>
  </BaserowTable>
</template>

<script>
import { ORIENTATIONS } from '@baserow/modules/builder/enums'
import BaserowTable from '@baserow/modules/builder/components/elements/components/BaserowTable'

export default {
  name: 'ABTable',
  components: { BaserowTable },
  props: {
    fields: {
      type: Array,
      required: true,
    },
    rows: {
      type: Array,
      required: true,
    },
    orientation: {
      type: String,
      required: false,
      default: ORIENTATIONS.HORIZONTAL,
    },
    contentLoading: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    emptyStateMessage() {
      return this.contentLoading
        ? this.$t('abTable.loading')
        : this.$t('abTable.empty')
    },
  },
}
</script>
