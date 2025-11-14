import JobService from '@baserow/modules/core/services/job'
import _ from 'lodash'

const FINISHED_STATES = ['finished', 'failed', 'cancelled']
const STARTING_TIMEOUT_MS = 200
const MAX_POLLING_ATTEMPTS = 100

/**
 * Calls job-type specific routine to enhance job object with any job-type specific
 * properties. This may return `null` if job type is not registered.
 *
 * @param job
 * @param registry
 * @returns {*|null}
 */
export function populateJob(job, registry) {
  const type = registry.get('job', job.type)
  return type.populate(job)
}

export const state = () => ({
  loaded: false,
  loading: false,
  refreshing: false,
  items: [],
  updateTimeoutId: null,
  nextTimeoutInMs: null,
  remainingPollingAttempts: MAX_POLLING_ATTEMPTS,
  lastUpdateJobIds: [],
})

export const mutations = {
  SET_LOADED(state, loaded) {
    state.loaded = loaded
  },
  SET_LOADING(state, loading) {
    state.loading = loading
  },
  SET_ITEMS(state, items) {
    state.items = items
  },
  /**
   * Adds new job to the store.
   * Adding job might be triggered from various places i.e. backend POST response
   * or from websocket message. In those cases we want to make sure we don't add
   * the same job multiple times.
   */
  ADD_ITEM(state, item) {
    const existingJobIndex = state.items.findIndex((job) => job.id === item.id)
    if (existingJobIndex === -1) {
      state.items.push(item)
    }
  },
  UPDATE_ITEM(state, { id, values }) {
    const index = state.items.findIndex((item) => item.id === id)
    if (index !== -1) {
      Object.assign(state.items[index], state.items[index], values)
    }
  },
  DELETE_ITEM(state, id) {
    const index = state.items.findIndex((item) => item.id === id)
    if (index !== -1) {
      state.items.splice(index, 1)
    }
  },
  COMPUTE_NEXT_TIMEOUT_MS(state, unfinishedJobIds) {
    const newJobsToUpdate = !_.isEqual(unfinishedJobIds, state.lastUpdateJobIds)
    const maxTimeout = this.$config.BASEROW_FRONTEND_JOBS_POLLING_TIMEOUT_MS
    if (unfinishedJobIds.length === 0) {
      // no unfinished jobs to update, so we can relax the refresh until
      // a new job is added.
      state.nextTimeoutInMs = maxTimeout
    } else if (newJobsToUpdate) {
      // we want to update quickly the UI for new jobs because they can
      // be very quickly.
      state.remainingPollingAttempts = MAX_POLLING_ATTEMPTS
      state.lastUpdateJobIds = unfinishedJobIds
      state.nextTimeoutInMs = STARTING_TIMEOUT_MS
    } else if (state.remainingPollingAttempts === 0) {
      // too many attempts, disable the poller until some other job needs updates.
      return null
    } else {
      // incrementally increase the timeout to decrease the rate
      // of the requests to the backend.
      state.remainingPollingAttempts -= 1
      state.nextTimeoutInMs = Math.floor(
        Math.min(state.nextTimeoutInMs * 1.5, maxTimeout)
      )
    }
  },
  SET_REFRESHING(state, refreshing) {
    state.refreshing = refreshing
  },
}

export const actions = {
  /**
   * Loads all the jobs from the backend to restore the UI for the pending jobs
   * and start the polling to update the jobs.
   */
  async initializePoller({ dispatch, state }) {
    if (!state.loaded && !state.loading) {
      await dispatch('fetchAllUnfinished')
    }
    if (!this.updateTimeoutId) {
      await dispatch('tryScheduleNextUpdate')
    }
  },
  /**
   * If the limit of attempts is not exceeded, schedule the next timeout to update
   * all unfinished job states.
   * It won't make a request to the backend if there are no pending jobs.
   */
  tryScheduleNextUpdate({ getters, commit, dispatch, state }) {
    if (!process.browser) return
    clearTimeout(this.updateTimeoutId)

    commit('SET_REFRESHING', true)

    const unfinishedJobs = getters.getUnfinishedJobs
    const unfinishedJobIds = unfinishedJobs
      ? unfinishedJobs.map((job) => job.id)
      : []
    commit('COMPUTE_NEXT_TIMEOUT_MS', unfinishedJobIds)
    const nextTimeoutInMs = state.nextTimeoutInMs
    // too many attempts for the same pending jobs, stop polling
    // at least until a new pending job is added
    if (nextTimeoutInMs === null) {
      return
    }
    this.updateTimeoutId = setTimeout(async () => {
      if (unfinishedJobIds.length > 0) {
        await dispatch('updateAllAndScheduleNext', unfinishedJobIds)
      }
      commit('SET_REFRESHING', false)
    }, nextTimeoutInMs)
  },
  /**
   * Fetch all unfinished jobs for the authenticated user.
   */
  async fetchAllUnfinished({ commit }) {
    commit('SET_LOADING', true)
    try {
      const { data } = await JobService(this.$client).fetchAll({
        states: FINISHED_STATES.map((item) => `!${item}`),
      })
      const items = []
      for (const job of data.jobs) {
        // not all the job types of the backend are mapped on the frontend
        // so skip the ones that doesn't have a related JobType
        try {
          this.$registry.get('job', job.type)
        } catch (e) {
          continue
        }

        items.push(populateJob(job, this.$registry))
      }
      commit('SET_ITEMS', items)
      commit('SET_LOADED', true)
    } catch {
      commit('SET_ITEMS', [])
    }
    commit('SET_LOADING', false)
  },
  /**
   * Dispatch the update for all the pending jobs and schedule the next update if
   * no error is raised from the backend.
   */
  async updateAllAndScheduleNext({ dispatch }, jobIds) {
    try {
      await dispatch('updateAll', jobIds)
      await dispatch('tryScheduleNextUpdate')
    } catch (error) {}
  },
  /**
   * Update the status of all the jobs in the store that are unfinished.
   */
  async updateAll({ commit, dispatch, getters, state }, jobIds = null) {
    if (jobIds === null) {
      jobIds = getters.getUnfinishedJobs.map((job) => job.id)
    }
    commit('SET_LOADING', true)

    try {
      const { data } = await JobService(this.$client).fetchAll({ jobIds })
      for (const job of data.jobs) {
        await dispatch('forceUpdate', { job, data: job })
      }
    } finally {
      commit('SET_LOADING', false)
    }
  },
  /**
   * Create a new job and add it to the store. It also restart the polling if neeeded.
   */
  create({ dispatch }, job) {
    dispatch('forceCreate', job)
    dispatch('tryScheduleNextUpdate')
    return this.getters['job/get'](job.id)
  },

  /**
   * Cancels a scheduled or running job.
   */
  async cancel({ dispatch }, { id }) {
    const job = this.getters['job/get'](id)
    if (!job) {
      throw new Error('Job not found in store.')
    }
    try {
      const { data } = await JobService(this.$client).cancel(job.id)
      await dispatch('forceUpdate', { job, data })
    } finally {
      await dispatch('tryScheduleNextUpdate')
    }
  },
  /**
   * Forcefully create an item in the store without making a call to the server.
   */
  forceCreate({ commit }, job) {
    populateJob(job, this.$registry)
    commit('ADD_ITEM', job)
  },
  /**
   * Forcefully update an item in the store without making a call to the server.
   */
  async forceUpdate({ commit }, { job, data }) {
    const type = this.$registry.get('job', job.type)
    await type.beforeUpdate(job, data)
    commit('UPDATE_ITEM', { id: job.id, values: data })
    await type.afterUpdate(job, data)
  },
  /**
   * Forcefully delete an item in the store without making a call to the server.
   */
  forceDelete({ commit }, job) {
    const type = this.$registry.get('job', job.type)
    type.beforeDelete(job, this)
    commit('DELETE_ITEM', job.id)
  },
  /**
   * Deletes all the jobs belonging to the given workspace.
   */
  deleteForWorkspace({ commit, state }, workspace) {
    const jobs = state.items.filter((job) =>
      this.$registry.get('job', job.type).isJobPartOfWorkspace(job, workspace)
    )
    jobs.forEach((job) => commit('DELETE_ITEM', job.id))
  },
  /**
   * Deletes all the jobs belonging to the given application.
   */
  deleteForApplication({ commit, state }, application) {
    const jobs = state.items.filter((job) =>
      this.$registry
        .get('job', job.type)
        .isJobPartOfApplication(job, application)
    )
    jobs.forEach((job) => commit('DELETE_ITEM', job.id))
  },
  clearAll({ commit, dispatch }) {
    clearTimeout(this.updateTimeoutId)
    commit('SET_ITEMS', [])
    commit('SET_LOADED', false)
  },
}

export const getters = {
  isLoading(state) {
    return state.loading
  },
  isLoaded(state) {
    return state.loaded
  },
  get: (state) => (id) => {
    return state.items.find((item) => item.id === id)
  },
  getAll: (state) => {
    return state.items
  },
  getUnfinishedJobs: (state) => {
    return state.items.filter((item) => !FINISHED_STATES.includes(item.state))
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
