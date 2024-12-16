<template>
  <div
    v-tooltip:[tooltipConfig]="tooltipContent"
    class="grid-view-aggregation__generic"
    tooltip-position="top"
  >
    <span class="grid-view-aggregation__generic-name">
      {{ aggregationType.getShortName() }}
    </span>
    <span
      class="grid-view-aggregation__generic-value"
      :class="{
        'grid-view-aggregation__generic-value--loading': loading,
      }"
    >
      {{ topItem }}
    </span>
  </div>
</template>

<script>
import { escape } from 'lodash'

export default {
  props: {
    aggregationType: {
      type: Object,
      required: true,
    },
    loading: {
      type: Boolean,
      default: false,
    },
    value: {
      type: Array,
      required: false,
      default: () => [],
    },
  },
  computed: {
    topItem() {
      if (this.value?.[0]) {
        return this.value[0].map(escape).join(' ')
      }
      return ''
    },
    tooltipContent() {
      if (this.value) {
        const tableRows = this.value.map((items) => {
          const rowCells = items.map((item) => `<td>${escape(item)}</td>`)
          return `<tr>${rowCells.join('')}</tr>`
        })
        return `<table>${tableRows.join('')}</table>`
      }
      return ''
    },
    tooltipConfig() {
      return {
        contentIsHtml: true,
        contentClasses: 'tooltip__content--expandable',
      }
    },
  },
}
</script>
