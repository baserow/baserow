<template>
  <component
    :is="chartComponent"
    v-if="chartData.datasets.length > 0"
    id="chart-id"
    :options="chartOptions"
    :data="chartData"
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
  props: {
    dataSource: {
      type: Object,
      required: true,
    },
    dataSourceData: {
      type: Object,
      required: true,
    },
    seriesConfig: {
      type: Array,
      required: true,
    },
  },
  computed: {
    chartComponent() {
      if (this.chartSeries.length > 0) {
        const firstSeriesConfig = this.getIndividualSeriesConfig(
          this.chartSeries[0].id
        )
        const chartType = this.convertChartJsType(
          firstSeriesConfig.series_chart_type
        )
        if (['pie', 'doughnut'].includes(chartType)) {
          return 'Pie'
        }
      }
      return 'Bar'
    },
    colorSeries() {
      return this.chartComponent === 'Bar'
    },
    chartOptions() {
      return {
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
                  const originalLabels = original.call(this, chart)
                  let datasetColors = chart.data.datasets.map(function (e) {
                    return e.backgroundColor
                  })
                  datasetColors = datasetColors.flat()
                  const newLabels = []
                  let colorOffset = 0
                  for (const dataset of chart.data.datasets) {
                    originalLabels.forEach((label) => {
                      const newLabel = JSON.parse(JSON.stringify(label))
                      newLabel.text = `${label.text} - ${dataset.label}`
                      newLabel.fillStyle =
                        datasetColors[label.index + colorOffset]
                      newLabels.push(newLabel)
                    })
                    colorOffset += dataset.data.length
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
    },
    result() {
      return this.dataSourceData.result
    },
    chartData() {
      if (!this.result) {
        return {
          datasets: [],
        }
      }
      if (this.dataSource.aggregation_group_bys?.length === 0) {
        return this.chartDataNoGrouping
      }
      return this.chartDataGrouping
    },
    chartDataGrouping() {
      const groupByFieldId = this.dataSource.aggregation_group_bys[0].field_id
      const primaryField = Object.values(
        this.dataSource.schema.properties
      ).find((item) => item.metadata?.primary === true)
      const labels = this.result.map((item) => {
        if (item[`field_${groupByFieldId}`] !== undefined) {
          return this.getGroupByValue(`field_${groupByFieldId}`, item)
        }
        return this.getGroupByValue(`field_${primaryField.metadata.id}`, item)
      })
      const datasets = []
      let colorOffset = 0
      for (const [index, series] of this.chartSeries.entries()) {
        const seriesData = this.result.map((item) => {
          return item[`${series.fieldName}_${series.aggregationType}`]
        })
        const label = this.getLabel(series.fieldName, series.aggregationType)
        const seriesConfig = this.getIndividualSeriesConfig(series.id)
        datasets.push({
          type:
            this.convertChartJsType(seriesConfig.series_chart_type) || 'bar',
          data: seriesData,
          label,
          ...this.chartColorsSeriesOrValues(index, colorOffset),
        })
        if (!this.colorSeries) {
          colorOffset += seriesData.length
        }
      }
      return {
        labels,
        datasets,
      }
    },
    chartDataNoGrouping() {
      const labels = ['']
      const datasets = []
      for (const [index, series] of this.chartSeries.entries()) {
        const seriesData = [
          this.result[`${series.fieldName}_${series.aggregationType}`],
        ]
        const label = this.getLabel(series.fieldName, series.aggregationType)
        const seriesConfig = this.getIndividualSeriesConfig(series.id)
        datasets.push({
          type:
            this.convertChartJsType(seriesConfig.series_chart_type) || 'bar',
          data: seriesData,
          label,
          ...this.chartColors[index],
        })
      }
      return {
        labels,
        datasets,
      }
    },
    chartSeries() {
      return this.dataSource.aggregation_series.map((item) => {
        return {
          id: item.id,
          fieldName: `field_${item.field_id}`,
          aggregationType: item.aggregation_type,
        }
      })
    },
    chartColors() {
      return [
        {
          backgroundColor: '#5190ef',
          borderColor: '#5190ef',
          hoverBackgroundColor: '#5190ef',
        },
        {
          backgroundColor: '#2BC3F1',
          borderColor: '#2BC3F1',
          hoverBackgroundColor: '#2BC3F1',
        },
        {
          backgroundColor: '#FFC744',
          borderColor: '#FFC744',
          hoverBackgroundColor: '#FFC744',
        },
        {
          backgroundColor: '#E26AB0',
          borderColor: '#E26AB0',
          hoverBackgroundColor: '#E26AB0',
        },
        {
          backgroundColor: '#3E4ACB',
          borderColor: '#3E4ACB',
          hoverBackgroundColor: '#3E4ACB',
        },
      ]
    },
  },
  methods: {
    chartColorsSeriesOrValues(index, offset) {
      if (this.colorSeries) {
        return this.chartColors[index]
      } else {
        return {
          backgroundColor: this.chartColors
            .slice(offset || 0)
            .map((item) => item.backgroundColor),
        }
      }
    },
    convertChartJsType(chartType) {
      if (!chartType) {
        return null
      }

      return chartType.toLowerCase()
    },
    getFieldTitle(fieldName) {
      return this.dataSource.schema.properties[fieldName].title
    },
    getAggregationTitle(aggregationType) {
      return this.$registry.get('viewAggregation', aggregationType).getName()
    },
    getLabel(fieldName, aggregationType) {
      let label = this.getAggregationTitle(aggregationType)
      if (fieldName) {
        label = `${this.getFieldTitle(fieldName)} (${label})`
      }
      return label
    },
    getGroupByValue(fieldName, item) {
      const serializedField = this.dataSource.context_data.fields[fieldName]
      const fieldType = serializedField.type

      if (item[fieldName] === 'OTHER_VALUES') {
        return this.$t('chart.other')
      }

      if (this.$registry.exists('chartFieldFormatting', fieldType)) {
        const fieldFormatter = this.$registry.get(
          'chartFieldFormatting',
          fieldType
        )
        return fieldFormatter.formatGroupByFieldValue(
          serializedField,
          item[fieldName]
        )
      }

      return item[fieldName] ?? ''
    },
    getIndividualSeriesConfig(seriesId) {
      return this.seriesConfig.find((item) => item.series_id === seriesId) || {}
    },
  },
}
</script>
