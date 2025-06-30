<template>
  <div
    v-tooltip:[tooltipConfig]="tooltipContent"
    class="grid-view-aggregation__generic grid-view-aggregation__distribution"
    tooltip-position="top"
    tooltip-top-value="4"
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
import { truncate } from 'lodash'

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
        return this.value[0]
          .map((v, index) =>
            index === 0
              ? v !== undefined
                ? this.fieldType.toAggregationString(this.field, v) ||
                  this.emptyCount
                : this.othersCount
              : v
          )
          .join(' ')
      }
      return ''
    },
    tooltipContent() {
      if (this.value) {
        const tableRows = this.value.map((items) => {
          return items.map((item, index) => {
            let displayValue
            if (index === 0) {
              if (item !== undefined) {
                displayValue =
                  this.fieldType.toAggregationString(this.field, item) ||
                  this.emptyCount
              } else {
                displayValue = this.othersCount
              }
            } else {
              displayValue = item
            }
            return truncate(displayValue, {
              length: 30,
              omission: '…',
            })
          })
        })
        return this.generateTable(tableRows)
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
    emptyCount() {
      return this.$i18n.t('viewAggregationType.emptyCount')
    },
  },
  methods: {
    generateTable(data) {
      if (!process.client) {
        return null
      }

      const table = document.createElement('table')
      for (const row of data) {
        const tr = document.createElement('tr')
        for (const cell of row) {
          const td = document.createElement('td')
          td.innerText = cell
          tr.appendChild(td)
        }
        table.appendChild(tr)
      }

      return table.outerHTML
    },
  },
}
</script>
