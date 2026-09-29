<template>
  <div
    class="grid-view__group-span"
    :style="{
      top: span.y + 'px',
      height: span.height + 'px',
      left: left + 'px',
      width: width + 'px',
    }"
  >
    <div class="grid-view__group-cell grid-view__group-cell--sticky">
      <div class="grid-view__group-value">
        <span v-if="isEmptyValue" class="grid-view__group-value-empty">
          {{ $t('gridViewGroupByBanner.emptyValue') }}
        </span>
        <component
          :is="groupByComponent"
          v-else-if="groupByComponent"
          :field="groupByField"
          :value="rowValueForGroup"
          :workspace-id="workspaceId"
        />
        <span v-else class="grid-view__group-value-text">
          {{ fallbackValueText }}
        </span>
      </div>
      <div class="grid-view__group-count">{{ span.rowCount }}</div>
    </div>
  </div>
</template>

<script>
import gridViewGroupByValue from '@baserow/modules/database/mixins/gridViewGroupByValue'

export default {
  name: 'GridViewGroupByColumnSpan',
  mixins: [gridViewGroupByValue],
  props: {
    span: { type: Object, required: true },
    groupByField: { type: Object, default: null },
    left: { type: Number, required: true },
    width: { type: Number, required: true },
    workspaceId: { type: null, default: null },
  },
  computed: {
    groupPath() {
      return this.span.path
    },
    groupDisplay() {
      return this.span.display
    },
  },
}
</script>
