<template>
  <template v-if="isClientReady">
    <component
      :is="chartComponent"
      v-if="hasChartData"
      id="chart-id"
      :key="chartRenderKey"
      :options="chartOptions"
      :data="data"
      class="chart"
    />

    <div v-else class="chart__no-data">
      <span class="chart__no-data-dashed-line"></span>
      <span class="chart__no-data-dashed-line"></span>
      <span class="chart__no-data-dashed-line"></span>
      <span class="chart__no-data-dashed-line"></span>
      <span class="chart__no-data-dashed-line"></span>
      <span class="chart__no-data-plain-line"></span>
    </div>
  </template>
</template>

<script>
import { Bar, Pie } from 'vue-chartjs'
import {
  Chart as ChartJS,
  ArcElement,
  LineElement,
  BarElement,
  PointElement,
  BarController,
  BubbleController,
  DoughnutController,
  LineController,
  PieController,
  PolarAreaController,
  RadarController,
  ScatterController,
  CategoryScale,
  LinearScale,
  LogarithmicScale,
  RadialLinearScale,
  TimeScale,
  TimeSeriesScale,
  Decimation,
  Filler,
  Legend,
  Title,
  Tooltip,
  SubTitle,
} from 'chart.js'
import { convertChartJsType } from '@baserow_premium/dashboard/chartData'

ChartJS.register(
  ArcElement,
  LineElement,
  BarElement,
  PointElement,
  BarController,
  BubbleController,
  DoughnutController,
  LineController,
  PieController,
  PolarAreaController,
  RadarController,
  ScatterController,
  CategoryScale,
  LinearScale,
  LogarithmicScale,
  RadialLinearScale,
  TimeScale,
  TimeSeriesScale,
  Decimation,
  Filler,
  Legend,
  Title,
  Tooltip,
  SubTitle
)

export default {
  name: 'Chart',
  components: { Bar, Pie },
  emits: ['rendered'],
  data() {
    return {
      isClientReady: false,
    }
  },
  props: {
    data: {
      type: Object,
      required: false,
      default: () => ({ datasets: [] }),
    },
    options: {
      type: Object,
      required: false,
      default: null,
    },
  },
  mounted() {
    this.isClientReady = true
    this.emitRendered()
  },
  updated() {
    if (this.isClientReady) {
      this.emitRendered()
    }
  },
  computed: {
    chartComponent() {
      const firstDatasetType = convertChartJsType(this.data.datasets?.[0]?.type)
      return ['pie', 'doughnut'].includes(firstDatasetType) ? 'Pie' : 'Bar'
    },
    hasChartData() {
      return this.data.datasets.length > 0
    },
    chartRenderKey() {
      return `${this.chartComponent}-${JSON.stringify(this.data)}`
    },
    chartOptions() {
      const options = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            align: 'start',
            position: 'bottom',
            labels: {
              usePointStyle: true,
              boxWidth: 14,
              pointStyle: 'circle',
              padding: 20,
              generateLabels: function (chart) {
                if (chart.config.type === 'bar') {
                  return Legend.defaults.labels.generateLabels(chart)
                } else {
                  const original =
                    ChartJS.overrides.pie.plugins.legend.labels.generateLabels
                  if (chart.data.datasets.length <= 1) {
                    return original.call(this, chart)
                  }
                  const originalLabels = original.call(this, chart)
                  const datasetColors = chart.data.datasets.map(function (e) {
                    return e.backgroundColor
                  })
                  let datasetIndex = 0
                  const newLabels = []
                  for (const dataset of chart.data.datasets) {
                    originalLabels.forEach((label) => {
                      const newLabel = JSON.parse(JSON.stringify(label))
                      if (label.text) {
                        newLabel.text = `${label.text} - ${dataset.label}`
                      } else {
                        newLabel.text = dataset.label
                      }
                      newLabel.fillStyle =
                        datasetColors[datasetIndex]?.[label.index % 10] ||
                        label.fillStyle
                      newLabels.push(newLabel)
                    })
                    datasetIndex += 1
                  }
                  return newLabels
                }
              },
            },
          },
          tooltip: {
            backgroundColor: '#202128',
            padding: 10,
            bodyFont: {
              size: 12,
            },
            titleFont: {
              size: 12,
            },
          },
        },
        elements: {
          bar: {
            borderRadius: {
              topLeft: 4,
              topRight: 4,
              bottomLeft: 0,
              bottomRight: 0,
            },
            borderWidth: 1,
            borderColor: '#5190ef',
            backgroundColor: '#5190ef',
            hoverBackgroundColor: '#5190ef',
          },
        },
      }

      return this.mergeOptions(options, this.options)
    },
  },
  methods: {
    mergeOptions(base, override) {
      if (!override) {
        return base
      }

      return Object.entries(override).reduce(
        (result, [key, value]) => {
          if (
            value &&
            typeof value === 'object' &&
            !Array.isArray(value) &&
            result[key] &&
            typeof result[key] === 'object' &&
            !Array.isArray(result[key])
          ) {
            result[key] = this.mergeOptions(result[key], value)
          } else {
            result[key] = value
          }
          return result
        },
        { ...base }
      )
    },
    emitRendered() {
      this.$nextTick(() => {
        const emitRendered = () => this.$emit('rendered')
        if (typeof window !== 'undefined' && window.requestAnimationFrame) {
          window.requestAnimationFrame(emitRendered)
        } else {
          emitRendered()
        }
      })
    },
  },
}
</script>
