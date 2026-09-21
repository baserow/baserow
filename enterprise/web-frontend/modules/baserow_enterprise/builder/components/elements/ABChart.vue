<template>
  <div ref="chart" class="ab-chart">
    <span ref="axisColor" class="ab-chart__axis-color" aria-hidden="true" />
    <Chart :data="data" :options="options" class="ab-chart__chart" />
  </div>
</template>

<script>
import Chart from '@baserow_premium/components/Chart'

export default {
  name: 'ABChart',
  components: { Chart },
  props: {
    data: {
      type: Object,
      required: true,
    },
    themeStyle: {
      type: Object,
      required: false,
      default: () => ({}),
    },
  },
  data() {
    return {
      themeValues: {},
    }
  },
  computed: {
    options() {
      return {
        plugins: {
          legend: {
            labels: {
              color: this.themeValues.label,
              font: {
                size: this.themeValues.fontSize,
              },
            },
          },
        },
        scales: {
          x: this.getAxisOptions(),
          y: this.getAxisOptions(),
        },
      }
    },
  },
  mounted() {
    this.updateThemeColors()
  },
  watch: {
    themeStyle: {
      deep: true,
      handler() {
        this.updateThemeColorsAfterStyleChange()
      },
    },
  },
  methods: {
    async updateThemeColorsAfterStyleChange() {
      await this.$nextTick()
      if (typeof requestAnimationFrame === 'undefined') {
        this.updateThemeColors()
      } else {
        requestAnimationFrame(() => this.updateThemeColors())
      }
    },
    updateThemeColors() {
      if (!this.$refs.chart || typeof getComputedStyle === 'undefined') {
        return
      }

      const styles = getComputedStyle(this.$refs.chart)
      const axisColorStyles = getComputedStyle(this.$refs.axisColor)
      const nextThemeValues = {
        axis: axisColorStyles.color,
        label: styles.color,
        fontSize: Number.parseFloat(styles.fontSize),
      }

      if (
        nextThemeValues.axis !== this.themeValues.axis ||
        nextThemeValues.label !== this.themeValues.label ||
        nextThemeValues.fontSize !== this.themeValues.fontSize
      ) {
        this.themeValues = nextThemeValues
      }
    },
    getAxisOptions() {
      return {
        border: {
          color: this.themeValues.label,
        },
        grid: {
          color: this.themeValues.axis,
        },
        ticks: {
          color: this.themeValues.label,
          font: {
            size: this.themeValues.fontSize,
          },
        },
      }
    },
  },
}
</script>
