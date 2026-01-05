import JobService from '@baserow/modules/core/services/job'

/**
 * DEPRECATED in favor of job.js.
 * To use this mixin you need to create the following methods on your component:
 * - `getCustomHumanReadableJobState(state)` returns the human readable message your
 *   custom state values.
 * - onJobUpdated() (optional) is called during the polling for not finished jobs.
 * - onJobDone() (optional) is called if the job successfully finishes.
 * - onJobFailed() (optional) is called if the job fails.
 * - onJobPollingError(error) (optional) is called if the polling fails.
 *
 */
export default {
  data() {
    return {
      job: null,
      nextPollTimeout: null,
      pollTimeoutId: null,
    }
  },
  computed: {
    jobHasSucceeded() {
      return this.job?.state === 'finished'
    },
    jobHasFailed() {
      return this.job?.state === 'failed'
    },
    jobIsFinished() {
      return this.jobHasSucceeded || this.jobHasFailed
    },
    jobIsRunning() {
      return this.job !== null && !this.jobIsFinished
    },

    jobHumanReadableState() {
      if (this.job === null) {
        return ''
      }
      const translations = {
        pending: this.$t('job.statePending'),
        started: this.$t('job.stateStarted'),
        failed: this.$t('job.stateFailed'),
        finished: this.$t('job.stateFinished'),
      }
      if (translations[this.job.state]) {
        return translations[this.job.state]
      }
      return this.getCustomHumanReadableJobState(this.job.state)
    },
  },
  methods: {
    /**
     * Call this method to start polling the job progress.
     *
     * @param {object} job the job you want to track.
     */
    startJobPoller(job) {
      this.job = job
      this.nextPollTimeout = 200
      this.pollTimeoutId = setTimeout(
        this.getLatestJobInfo,
        this.nextPollTimeout
      )
    },
    async getLatestJobInfo() {
      try {
        const { data: job } = await JobService(this.$client).get(this.job.id)
        this.job = job
        if (job.state === 'failed') {
          if (typeof this.onJobFailed === 'function') {
            await this.onJobFailed()
          }
        } else if (job.state === 'finished') {
          if (typeof this.onJobDone === 'function') {
            await this.onJobDone()
          }
        } else {
          // job unfinished, keep polling
          if (typeof this.onJobUpdated === 'function') {
            await this.onJobUpdated()
          }
          this.nextPollTimeout = Math.min(
            this.nextPollTimeout * 1.5,
            this.$config.public.baserowFrontendJobsPollingTimeoutMs
          )
          this.pollTimeoutId = setTimeout(
            this.getLatestJobInfo,
            this.nextPollTimeout
          )
        }
      } catch (error) {
        if (typeof this.onJobPollingError === 'function') {
          this.onJobPollingError(error)
        }
        this.job = null
      }
    },
    stopPollIfRunning() {
      if (this.pollTimeoutId) {
        clearTimeout(this.pollTimeoutId)
        this.pollTimeoutId = null
      }
    },
  },
}
