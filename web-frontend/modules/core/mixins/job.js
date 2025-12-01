/**
 * This mixin provides basic job control capabilities using job store.
 *
 * The purpose is to centralize job state management using job store. Components that
 * use this mixin are responsible for job object creation and adding it to the store.
 * This is because specific jobs are created using domain-specific API endpoints and not
 * using generic jobs API. A job that has been created should be added to the store
 * with createAndMonitorJob method during component's initialization.
 *
 * Job state changes are handled with callbacks. A component that want to use this
 * mixin should provide following methods:
 * - onJobFinished() (optional) is called if the job successfully finishes.
 * - onJobFailed() (optional) is called if the job fails.
 * - onJobCancelled() (optional) is called if a job has been cancelled.
 * - onJobCancelFailed() (optional) is called when a job cancellation request failed.
 * - showError({error,message}) handles an error. This can be provided by `error` mixin,
 *   but a class can provide own implementation here.
 * - `getCustomHumanReadableJobState(state)` returns the human readable message your
 *   custom state values. This mixin provides a default implementation.
 *
 */
export default {
  data() {
    return {
      job: null,
      cancelLoading: false,
    }
  },
  computed: {
    jobHasFailed() {
      return this.job?.state === 'failed' || this.job?.state === 'cancelled'
    },
    jobIsEnded() {
      return this.jobIsFinished || this.jobHasFailed
    },
    jobIsFinished() {
      return this.job?.state === 'finished'
    },
    jobIsRunning() {
      return this.job !== null && !this.jobIsEnded
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
        cancelled: this.$t('job.stateCanceled'),
      }
      if (translations[this.job.state]) {
        return translations[this.job.state]
      }
      return this.getCustomHumanReadableJobState(this.job.state)
    },
  },
  watch: {
    'job.state'(newState) {
      switch (newState) {
        case 'finished':
          if (typeof this.onJobFinished === 'function') {
            this.onJobFinished()
          }
          break
        case 'failed':
          if (typeof this.onJobFailed === 'function') {
            this.onJobFailed()
          }
          break
        case 'cancelled':
          if (typeof this.onJobCancelled === 'function') {
            this.onJobCancelled()
          }
          break
      }
    },
  },
  methods: {
    /**
     * This method adds a job object created externally to job store.
     *
     * A job object is created by a call to an endpoint that creates a task of a
     * specific type in the background because there's no generic job creation endpoint.
     * It's up to a component to call appropriate service/endpoint to trigger/schedule
     * a job.
     *
     * @param job a Job object
     * @returns {Promise<void>}
     */
    async createAndMonitorJob(job) {
      this.job = await this.$store.dispatch('job/create', job)
    },
    /**
     * Called from a component to cancel any job currently running.
     *
     * This method can receive error from the dispatch call. The error will be handled
     * by showError implementation. By default, if cancellation operation was performed
     * successfully, no status/error should be returned here.
     *
     * @returns {Promise<void>}
     */
    async cancelJob() {
      if (!this.jobIsRunning) {
        return
      }
      this.cancelLoading = true
      try {
        await this.$store.dispatch('job/cancel', {
          id: this.job.id,
        })
      } catch (error) {
        const errMsg = error.response?.data
        if (typeof this.showError === 'function') {
          if (errMsg?.error === 'ERROR_JOB_NOT_CANCELLABLE') {
            this.showError(
              this.$t('job.errorJobCannotBeCancelledTitle'),
              this.$t('job.errorJobCannotBeCancelledDescription')
            )
          } else {
            this.showError({
              title: this.$t('clientHandler.notCompletedTitle'),
              message:
                (error ? error?.detail || error?.message : null) ||
                this.$t('unknown error'),
            })
          }
          if (this.onJobCancelFailed === 'function') {
            this.onJobCancelFailed()
          }
        }
      } finally {
        this.cancelLoading = false
      }
    },
  },
}
