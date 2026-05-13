<template>
  <component
    :is="chartComponent"
    v-if="hasChartData"
    id="chart-id"
    :key="chartRenderKey"
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
import { colorPalette, getBaseColors } from '@baserow/modules/core/utils/colors'
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
  emits: ['rendered'],
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
  mounted() {
    this.emitRendered()
  },
  updated() {
    this.emitRendered()
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
                  if (chart.data.datasets.length <= 1) {
                    return original(chart)
                  }
                  const originalLabels = original(chart)
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
    },
    results() {
      return this.dataSourceData.results
    },
    hasGrouping() {
      return (this.dataSource.aggregation_group_bys || []).length > 0
    },
    chartData() {
      if (!this.results) {
        return {
          datasets: [],
        }
      }
      if (!this.hasGrouping) {
        return this.chartDataNoGrouping
      }
      return this.chartDataGrouping
    },
    hasChartData() {
      return this.chartData.datasets.length > 0
    },
    chartRenderKey() {
      return `${this.chartComponent}-${JSON.stringify(this.chartData)}`
    },
    serviceType() {
      if (!this.dataSource.type) {
        return null
      }
      return this.$registry.get('service', this.dataSource.type)
    },
    chartDataGrouping() {
      const groupByFieldId = this.dataSource.aggregation_group_bys[0].field_id
      const primaryField = Object.values(
        this.dataSource.schema.items.properties
      ).find((item) => item.metadata?.primary === true)
      const labels = this.results.map((item) => {
        const groupByFieldName = `field_${groupByFieldId}`
        const groupByResultName = this.getResultPropertyName(groupByFieldName)
        if (this.hasResultValue(item, groupByResultName, groupByFieldName)) {
          return this.getGroupByValue(groupByFieldName, groupByResultName, item)
        }
        const primaryFieldName = `field_${primaryField.metadata.id}`
        const primaryResultName = this.getResultPropertyName(primaryFieldName)
        return this.getGroupByValue(primaryFieldName, primaryResultName, item)
      })
      const datasets = []
      for (const [index, series] of this.chartSeries.entries()) {
        const technicalResultFieldName = `${series.fieldName}_${series.aggregationType}`
        const resultFieldName = this.getResultPropertyName(
          technicalResultFieldName
        )
        const seriesData = this.results.map((item) => {
          return this.getResultValue(
            item,
            resultFieldName,
            technicalResultFieldName
          )
        })
        const label = this.getLabel(series)
        const seriesConfig = this.getIndividualSeriesConfig(series.id)
        datasets.push({
          type:
            this.convertChartJsType(seriesConfig.series_chart_type) || 'bar',
          data: seriesData,
          label,
          ...this.chartColorsSeriesOrValues(index),
        })
      }
      return {
        labels,
        datasets,
      }
    },
    chartDataNoGrouping() {
      const result = this.results[0] || {}
      if (this.chartComponent === 'Pie') {
        const labels = []
        const data = []
        for (const series of this.chartSeries) {
          const technicalResultFieldName = `${series.fieldName}_${series.aggregationType}`
          const resultFieldName = this.getResultPropertyName(
            technicalResultFieldName
          )
          labels.push(this.getLabel(series))
          data.push(
            this.getResultValue(
              result,
              resultFieldName,
              technicalResultFieldName
            )
          )
        }
        return {
          labels,
          datasets: [
            {
              data,
              backgroundColor: this.valuesColors[0],
            },
          ],
        }
      }

      const labels = ['']
      const datasets = []
      for (const [index, series] of this.chartSeries.entries()) {
        const technicalResultFieldName = `${series.fieldName}_${series.aggregationType}`
        const resultFieldName = this.getResultPropertyName(
          technicalResultFieldName
        )
        const seriesData = [
          this.getResultValue(
            result,
            resultFieldName,
            technicalResultFieldName
          ),
        ]
        const label = this.getLabel(series)
        const seriesConfig = this.getIndividualSeriesConfig(series.id)
        datasets.push({
          type:
            this.convertChartJsType(seriesConfig.series_chart_type) || 'bar',
          data: seriesData,
          label,
          ...this.seriesColors[index],
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
          fieldId: item.field_id,
          fieldName: `field_${item.field_id}`,
          aggregationType: item.aggregation_type,
        }
      })
    },
    seriesColors() {
      return getBaseColors().map((color) => {
        return {
          backgroundColor: color,
          borderColor: color,
          hoverBackgroundColor: color,
        }
      })
    },
    valuesColors() {
      return colorPalette.map((palette) => {
        return [
          palette[4].color,
          palette[6].color,
          palette[8].color,
          palette[0].color,
          palette[2].color,
          palette[9].color,
          palette[7].color,
          palette[5].color,
          palette[3].color,
          palette[1].color,
        ]
      })
    },
  },
  methods: {
    chartColorsSeriesOrValues(seriesIndex) {
      if (this.colorSeries) {
        return this.seriesColors[seriesIndex]
      } else {
        return {
          backgroundColor: this.valuesColors[seriesIndex],
        }
      }
    },
    convertChartJsType(chartType) {
      if (!chartType) {
        return null
      }

      return chartType.toLowerCase()
    },
    getAggregationTitle(aggregationType) {
      return this.$registry.get('groupedAggregation', aggregationType).getName()
    },
    getResultField(series) {
      const resultFieldName = `${series.fieldName}_${series.aggregationType}`
      return this.dataSource.schema.items.properties[resultFieldName]
    },
    getFieldTitle(series) {
      const resultFieldName = `${series.fieldName}_${series.aggregationType}`
      return (
        this.serviceType?.getSchemaPropertyDisplayName(
          this.dataSource,
          resultFieldName
        ) || this.getResultField(series)?.title
      )
    },
    getLabel(series) {
      const label = this.getAggregationTitle(series.aggregationType)
      const fieldTitle = this.getFieldTitle(series)
      if (fieldTitle) {
        return `${fieldTitle} (${label})`
      }
      return label
    },
    getResultPropertyName(propertyName) {
      const property = this.dataSource.schema?.items?.properties?.[propertyName]
      if (property?.metadata?.aggregation) {
        return property.metadata.display_name || property?.title || propertyName
      }
      return property?.title || propertyName
    },
    hasResultValue(item, resultFieldName, fallbackFieldName = null) {
      return (
        item[resultFieldName] !== undefined ||
        (fallbackFieldName !== null && item[fallbackFieldName] !== undefined)
      )
    },
    getResultValue(item, resultFieldName, fallbackFieldName = null) {
      if (item[resultFieldName] !== undefined) {
        return item[resultFieldName]
      }
      if (fallbackFieldName !== null) {
        return item[fallbackFieldName]
      }
      return undefined
    },
    getGroupByValue(fieldName, resultFieldName, item) {
      const serializedField = this.dataSource.context_data.fields[fieldName]
      const fieldType = serializedField.type
      const value = this.getResultValue(item, resultFieldName, fieldName)

      if (value === 'OTHER_VALUES') {
        return this.$t('chart.other')
      }

      if (this.$registry.exists('chartFieldFormatting', fieldType)) {
        const fieldFormatter = this.$registry.get(
          'chartFieldFormatting',
          fieldType
        )
        return fieldFormatter.formatGroupByFieldValue(serializedField, value)
      }

      if (value === true) {
        return this.$t('chart.true')
      }

      if (value === false) {
        return this.$t('chart.false')
      }

      return value ?? ''
    },
    getIndividualSeriesConfig(seriesId) {
      return this.seriesConfig.find((item) => item.series_id === seriesId) || {}
    },
    emitRendered() {
      this.$nextTick(() => {
        this.$emit('rendered')
      })
    },
  },
}
</script>
