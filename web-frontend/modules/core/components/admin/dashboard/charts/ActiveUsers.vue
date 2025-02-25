<template>
  <LineChart :options="chartOptions" :data="chartData" class="active-users" />
</template>

<script>
import { Line as LineChart } from 'vue-chartjs'
import {
  Chart,
  Title,
  Tooltip,
  Legend,
  PointElement,
  LineElement,
  CategoryScale,
  LinearScale,
  TimeScale,
} from 'chart.js'

import 'chartjs-adapter-moment'

Chart.register(
  Title,
  Tooltip,
  Legend,
  PointElement,
  LineElement,
  CategoryScale,
  LinearScale,
  TimeScale
)

export default {
  components: { LineChart },
  props: {
    newUsers: {
      type: Array,
      required: true,
    },
    activeUsers: {
      type: Array,
      required: true,
    },
  },
  computed: {
    chartData() {
      const labels = []
      const day = 24 * 60 * 60 * 1000
      for (let i = 0; i < 30; i++) {
        const date = new Date(new Date().getTime() - day * i)
        labels.unshift(date.toISOString().substr(0, 10))
      }

      const newUserData = this.mapCount(labels, this.newUsers)
      const activeUserData = this.mapCount(labels, this.activeUsers)

      return {
        labels,
        datasets: [
          {
            label: this.$t('activeUsers.newUsers'),
            borderColor: '#59cd90',
            backgroundColor: 'transparent',
            color: '#9bf2c4',
            data: newUserData,
          },
          {
            label: this.$t('activeUsers.activeUsers'),
            borderColor: '#198dd6',
            backgroundColor: 'transparent',
            color: '#b4bac2',
            data: activeUserData,
          },
        ],
      }
    },
    chartOptions() {
      return {
        responsive: true,
        maintainAspectRatio: false,
        tension: 0.4,
        plugins: {
          legend: {
            align: 'start',
            position: 'bottom',
          },
        },
        scales: {
          x: {
            type: 'time',
            time: {
              parser: 'YYYY-MM-DD',
              displayFormats: {
                day: 'MMM D',
              },
              tooltipFormat: 'MMM D',
              unit: 'day',
            },
          },
        },
      }
    },
  },
  methods: {
    mapCount(labels, values) {
      return labels.map((date1) => {
        for (let i = 0; i < values.length; i++) {
          if (date1 === values[i].date) {
            return values[i].count
          }
        }
        return 0
      })
    },
  },
}
</script>
