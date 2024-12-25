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
import { escape, truncate } from 'lodash'

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
    field: {
      type: Object,
      required: true,
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
        console.log('>> this.value', this.value)
        const tableRows = this.value.map((items) => {
          const rowCells = items.map((item, index) => {
            let displayValue
            if (index === 0) {
              if (item) {
                displayValue = this.fieldType.toHumanReadableString(
                  this.field,
                  item
                )
              } else {
                displayValue = this.othersCount
              }
            } else {
              displayValue = item
            }
            return `<td>${truncate(escape(displayValue), {
              length: 30,
              omission: '…',
            })}</td>`
          })
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
    fieldType() {
      return this.$registry.get('field', this.field.type)
    },
    othersCount() {
      return this.$i18n.t('viewAggregationType.othersCount')
    },
  },
}
</script>
