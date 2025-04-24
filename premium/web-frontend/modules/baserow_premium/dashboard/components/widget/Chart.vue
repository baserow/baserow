<template>
  <Bar
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
import { Bar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  Title,
  Tooltip,
  Legend,
  BarElement,
  LineElement,
  CategoryScale,
  LinearScale,
  PointElement,
} from 'chart.js'

ChartJS.register(
  Title,
  Tooltip,
  Legend,
  BarElement,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement
)

export default {
  name: 'Chart',
  components: { Bar },
  props: {
    dataSource: {
      type: Object,
      required: true,
    },
    dataSourceData: {
      type: Object,
      required: true,
    },
  },
  computed: {
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
      for (const [index, series] of this.seriesConfig.entries()) {
        const seriesData = this.result.map((item) => {
          return item[`${series.fieldName}_${series.aggregationType}`]
        })
        const label = this.getLabel(series.fieldName, series.aggregationType)
        datasets.push({
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
    chartDataNoGrouping() {
      const labels = ['']
      const datasets = []
      for (const [index, series] of this.seriesConfig.entries()) {
        const seriesData = [
          this.result[`${series.fieldName}_${series.aggregationType}`],
        ]
        const label = this.getLabel(series.fieldName, series.aggregationType)
        datasets.push({
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
    seriesConfig() {
      return this.dataSource.aggregation_series.map((item) => {
        return {
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
  },
}
</script>
