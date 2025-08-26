<template>
  <div
    class="calendar-card"
    @click="$emit('edit-row', row)"
    @contextmenu.prevent="$emit('row-context', { row, event: $event })"
  >
    <RecursiveWrapper
      :components="
        wrapperDecorations.map((comp) => ({
          ...comp,
          props: comp.propsFn(row),
        }))
      "
    >
      <div class="calendar-card__content">
        <component
          :is="dec.component"
          v-for="dec in firstCellDecorations"
          :key="dec.decoration.id"
          v-bind="dec.propsFn(row)"
        />
        <div class="calendar-card__labels">
          {{ labelsText }}
        </div>
      </div>
    </RecursiveWrapper>
  </div>
</template>

<script>
import {
  sortFieldsByOrderAndIdFunction,
  filterVisibleFieldsFunction,
} from '@baserow/modules/database/utils/view'
import RecursiveWrapper from '@baserow/modules/core/components/RecursiveWrapper'

export default {
  name: 'CalendarCard',
  components: { RecursiveWrapper },
  props: {
    row: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    storePrefix: {
      type: String,
      required: true,
    },
    decorationsByPlace: {
      type: Object,
      required: false,
      default: () => undefined,
    },
  },
  computed: {
    visibleCardFields() {
      const fieldOptions =
        this.$store.getters[
          this.storePrefix + 'view/calendar/getAllFieldOptions'
        ]
      return this.fields
        .filter(filterVisibleFieldsFunction(fieldOptions))
        .sort(sortFieldsByOrderAndIdFunction(fieldOptions))
    },
    labelsText() {
      return this.visibleCardFields
        .map((f) => {
          const fieldType = this.$registry.get('field', f.type)
          const cellValue = this.row[`field_${f.id}`]
          return fieldType.toHumanReadableString(f, cellValue)
        })
        .join(' - ')
    },
    firstCellDecorations() {
      return this.decorationsByPlace?.first_cell || []
    },
    wrapperDecorations() {
      return this.decorationsByPlace?.wrapper || []
    },
  },
}
</script>
