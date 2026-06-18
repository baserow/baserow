<template>
  <div class="graph-element" :style="graphStyle">
    <ABChart
      v-if="chartData.datasets.length > 0"
      :data="chartData"
      :theme-style="graphStyle"
      class="graph-element__chart"
    />
    <div v-else class="graph-element__empty">
      {{ $t('graphElement.noData') }}
    </div>
  </div>
</template>

<script>
import { toRefs } from 'vue'
import { useElement } from '@baserow/modules/builder/composables/useElement'
import ABChart from '@baserow_enterprise/builder/components/elements/ABChart'
import { getBaseColors, resolveColor } from '@baserow/modules/core/utils/colors'
import {
  ensureArray,
  ensureString,
} from '@baserow/modules/core/utils/validator'

export default {
  name: 'GraphElement',
  components: { ABChart },
  props: {
    element: {
      type: Object,
      required: true,
    },
    applicationContextAdditions: {
      type: Object,
      required: false,
      default: undefined,
    },
  },
  setup(props) {
    const { colorVariables, getStyleOverride, resolveFormula } = useElement(
      toRefs(props)
    )

    return {
      colorVariables,
      getStyleOverride,
      resolveFormula,
    }
  },
  computed: {
    graphStyle() {
      return this.getStyleOverride('graph')
    },
    chartData() {
      const labels = ensureArray(this.resolveFormula(this.element.labels)).map(
        ensureString
      )
      const colors = getBaseColors()
      const datasets = (this.element.series || [])
        .map((series, index) => {
          const color = series.color
            ? resolveColor(series.color, this.colorVariables)
            : colors[index % colors.length]
          const data = ensureArray(this.resolveFormula(series.values)).map(
            (value) => {
              const numberValue = Number(value)
              return Number.isFinite(numberValue) ? numberValue : null
            }
          )

          return {
            type: this.convertChartJsType(series.chart_type),
            label:
              ensureString(this.resolveFormula(series.label)) ||
              this.$t('graphElement.series', { number: index + 1 }),
            data,
            borderColor: color,
            backgroundColor: color,
            hoverBackgroundColor: color,
            tension: 0.25,
          }
        })
        .filter((series) => series.data.length > 0)

      return {
        labels,
        datasets,
      }
    },
  },
  methods: {
    convertChartJsType(chartType) {
      return chartType === 'LINE' ? 'line' : 'bar'
    },
  },
}
</script>
