import { getHumanPeriodAgoCount } from '@baserow/modules/core/utils/date'

export default {
  props: {
    lastUpdated: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      timeAgo: '',
      refreshPeriod: null,
      timeoutHandler: null,
    }
  },
  mounted() {
    this.updateTimeAgo()
  },
  beforeDestroy() {
    clearTimeout(this.timeoutHandler)
  },
  methods: {
    updateTimeAgo() {
      const { period, count } = getHumanPeriodAgoCount(this.lastUpdated)

      if (period === 'seconds' && count <= 5) {
        this.timeAgo = this.$t('datetime.justNow')
        this.refreshPeriod = 5 * 1000
      } else if (period === 'seconds') {
        this.timeAgo = this.$t('datetime.lessThanMinuteAgo')
        this.refreshPeriod = 60 * 1000
      } else {
        this.timeAgo = this.$tc(`datetime.${period}Ago`, count)
        this.refreshPeriod = period === 'minutes' ? 60 * 1000 : 3600 * 1000
      }

      if (this.refreshPeriod) {
        this.scheduleNextUpdate()
      }
    },
    scheduleNextUpdate() {
      clearTimeout(this.timeoutHandler)
      this.timeoutHandler = setTimeout(() => {
        this.updateTimeAgo()
      }, this.refreshPeriod)
    },
  },
}
