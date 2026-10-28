import chatRunsService from '@baserow/modules/core/services/chatRuns'
import {
  CHAT_RUNS_PAGE,
  MAX_RECONNECT_ATTEMPTS,
  MAX_FINISHED_FOLLOWERS,
  RUN_FINISHED,
  RUN_HEARTBEAT,
  STATUS_CHECK_MS,
  STREAM_IDLE_MS,
  isTerminalStatus,
} from '@baserow/modules/core/chatRuns/constants'
import {
  compareCursors,
  parseCursor,
} from '@baserow/modules/core/chatRuns/cursor'
import {
  foldRunEvent,
  initialRunView,
} from '@baserow/modules/core/chatRuns/fold'

// Requests and timers are owned by the store, never by a mounted chat panel, and
// never enter serialized Vuex state. A WeakMap also isolates independent apps/tests.
const runtimes = new WeakMap()
function runtime(store, runId) {
  if (!runtimes.has(store)) runtimes.set(store, new Map())
  const runs = runtimes.get(store)
  if (!runs.has(runId)) runs.set(runId, { generation: 0 })
  return runs.get(runId)
}
function stopRuntime(store, runId) {
  const current = runtime(store, runId)
  clearTimeout(current.timer)
  current.controller?.abort()
  current.controller = null
}
/** End a stream that delivered nothing for too long, so it can reconnect. */
function restartIfSilent(store, runId) {
  const { controller, lastRecordAt } = runtime(store, runId)
  if (!controller || Date.now() - lastRecordAt < STREAM_IDLE_MS) return
  controller.abort()
  // An adopted stream belongs to the product's request, not to `connect`.
  store.dispatch('chatRuns/streamEnded', { runId, controller })
}
/** Read the status of a follower without a stream; an open stream reports it. */
function scheduleStatus(store, runId) {
  const follower = store.state.chatRuns.followers[runId]
  if (!import.meta.client || !follower || follower.finished) return
  const current = runtime(store, runId)
  if (current.suspended) return
  clearTimeout(current.timer)
  current.timer = setTimeout(() => {
    if (!store.getters['auth/isAuthenticated']) {
      stopRuntime(store, runId)
    } else if (follower.streaming) {
      restartIfSilent(store, runId)
      scheduleStatus(store, runId)
    } else {
      store.dispatch('chatRuns/checkStatus', runId)
    }
  }, STATUS_CHECK_MS)
}
const pageParameters = ({ runType, chatId }) => ({
  run_type: runType,
  chat_id: chatId,
})
// A confirmation from another socket means lifecycle messages may have been missed.
const subscriptionSockets = new WeakMap()
function sockets(store) {
  if (!subscriptionSockets.has(store)) subscriptionSockets.set(store, new Map())
  return subscriptionSockets.get(store)
}

export const state = () => ({ followers: {}, subscriptions: {} })

export const mutations = {
  ADD_FOLLOWER(state, follower) {
    state.followers[follower.runId] = follower
  },
  UPDATE_FOLLOWER(state, { runId, values }) {
    if (state.followers[runId]) Object.assign(state.followers[runId], values)
  },
  REMOVE_FOLLOWER(state, runId) {
    delete state.followers[runId]
  },
  SET_SUBSCRIPTION(state, { runType, chatId }) {
    state.subscriptions[runType] = chatId
  },
  REMOVE_SUBSCRIPTION(state, runType) {
    delete state.subscriptions[runType]
  },
}

export const actions = {
  /** Follow the runs other tabs start in one chat per run type. */
  subscribeToChat({ state, commit }, { runType, chatId }) {
    const current = state.subscriptions[runType]
    if (current === chatId) return
    const realtime = this.app.$realtime
    if (current !== undefined) {
      realtime.unsubscribe(
        CHAT_RUNS_PAGE,
        pageParameters({ runType, chatId: current })
      )
    }
    realtime.subscribe(CHAT_RUNS_PAGE, pageParameters({ runType, chatId }))
    sockets(this).set(runType, realtime.connected ? realtime.socket : null)
    commit('SET_SUBSCRIPTION', { runType, chatId })
  },

  unsubscribeFromChat({ state, commit }, { runType, chatId }) {
    if (state.subscriptions[runType] !== chatId) return
    this.app.$realtime.unsubscribe(
      CHAT_RUNS_PAGE,
      pageParameters({ runType, chatId })
    )
    sockets(this).delete(runType)
    commit('REMOVE_SUBSCRIPTION', runType)
  },

  /** Register a run, optionally adopting the original send's already-open stream. */
  follow(
    { state, commit, dispatch },
    { runId, runType, chatId, context = {}, controller = null, attach = true }
  ) {
    if (!state.followers[runId]) {
      const type = this.$registry.get('chatRunType', runType)
      commit('ADD_FOLLOWER', {
        runId,
        runType,
        chatId,
        context,
        followedAt: Date.now(),
        cursor: null,
        view: { ...initialRunView(), ...type.getInitialView() },
        finished: false,
        streaming: false,
        checkingStatus: false,
        reconnectAttempts: 0,
        replayUnavailable: false,
        stopRequested: false,
      })
    }
    const follower = state.followers[runId]
    if (follower.finished) return
    runtime(this, runId).suspended = false
    commit('UPDATE_FOLLOWER', {
      runId,
      values: { context: { ...follower.context, ...context } },
    })
    if (controller) {
      const previous = runtime(this, runId).controller
      if (previous && previous !== controller) previous.abort()
      runtime(this, runId).controller = controller
      runtime(this, runId).lastRecordAt = Date.now()
      commit('UPDATE_FOLLOWER', { runId, values: { streaming: true } })
    }
    scheduleStatus(this, runId)
    // The stream ends at once with the saved result of a run that already ended.
    if (attach && !follower.streaming) dispatch('connect', runId)
  },

  /** Open only a read-only follower; reconnect never calls a product send API. */
  connect({ state, commit, dispatch }, runId) {
    const follower = state.followers[runId]
    if (
      !follower ||
      follower.finished ||
      follower.streaming ||
      follower.replayUnavailable ||
      runtime(this, runId).suspended ||
      follower.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS
    ) {
      return
    }
    const controller = new AbortController()
    runtime(this, runId).controller = controller
    runtime(this, runId).lastRecordAt = Date.now()
    commit('UPDATE_FOLLOWER', {
      runId,
      values: {
        streaming: true,
        reconnectAttempts: follower.reconnectAttempts + 1,
      },
    })
    const type = this.$registry.get('chatRunType', follower.runType)
    // The promise remains owned here after the UI closes.
    Promise.resolve()
      .then(() =>
        type.openStream(
          follower,
          (record) => dispatch('acceptRecord', { runId, record, controller }),
          controller.signal
        )
      )
      .catch((error) => {
        if (runtimes.get(this)?.get(runId)?.controller !== controller) return
        if ([401, 403, 404].includes(error.response?.status)) {
          dispatch('unavailable', runId)
        }
      })
      .finally(() => dispatch('streamEnded', { runId, controller }))
  },

  streamEnded({ state, commit, dispatch }, { runId, controller }) {
    const follower = state.followers[runId]
    if (!follower) return
    const current = runtime(this, runId)
    if (current.controller !== controller) return
    current.controller = null
    commit('UPDATE_FOLLOWER', { runId, values: { streaming: false } })
    if (!follower.finished && !current.suspended) {
      dispatch('checkStatus', runId)
    }
  },

  /** Fold ordered records; cursor gaps are normal Redis IDs, duplicates are not. */
  acceptRecord({ state, commit, dispatch }, { runId, record, controller }) {
    const follower = state.followers[runId]
    if (!follower || follower.finished) return
    const current = runtime(this, runId)
    if (
      current.suspended ||
      !this.getters['auth/isAuthenticated'] ||
      (controller && current.controller !== controller)
    ) {
      return
    }
    current.lastRecordAt = Date.now()
    const type = this.$registry.get('chatRunType', follower.runType)
    const metadata = type.getRecordMetadata(record) || {}
    if (metadata.id && metadata.id !== runId) return
    const event = type.getRecordEvent(record)
    if (event?.kind === RUN_HEARTBEAT) return
    // A terminal record comes from the committed primary outcome, even when the
    // temporary buffer or its cursor has become unusable.
    if (event?.kind === RUN_FINISHED) {
      return dispatch('applySnapshot', { runId, snapshot: event.data })
    }
    if (
      metadata.replay_unavailable ||
      event?.kind === 'run.replay_unavailable'
    ) {
      commit('UPDATE_FOLLOWER', { runId, values: { replayUnavailable: true } })
      dispatch('checkStatus', runId)
      return
    }
    if (follower.replayUnavailable && !metadata.reset) return
    const nextCursor = metadata.cursor
    if (nextCursor) {
      const comparison = follower.cursor
        ? compareCursors(nextCursor, follower.cursor)
        : 1
      if (
        !parseCursor(nextCursor) ||
        (comparison === null && !metadata.reset)
      ) {
        commit('UPDATE_FOLLOWER', {
          runId,
          values: { replayUnavailable: true },
        })
        dispatch('checkStatus', runId)
        return
      }
      // A committed terminal record can carry the last output cursor too.
      if (comparison !== null && comparison <= 0 && !metadata.reset) {
        return
      }
      if (metadata.reset) {
        // A baseline rebuilds output only; the run's lifecycle is not in it.
        const { status, cancelRequested } = follower.view
        commit('UPDATE_FOLLOWER', {
          runId,
          values: {
            view: {
              ...initialRunView(),
              ...type.getInitialView(),
              status,
              cancelRequested,
            },
            replayUnavailable: false,
          },
        })
      }
      commit('UPDATE_FOLLOWER', {
        runId,
        values: {
          cursor: nextCursor,
          ...(comparison > 0 ? { reconnectAttempts: 0 } : {}),
        },
      })
    }
    if (event?.kind) {
      commit('UPDATE_FOLLOWER', {
        runId,
        values: {
          view: type.foldEvent(foldRunEvent(follower.view, event), event),
        },
      })
      type.onEvent(
        follower,
        event,
        !metadata.replay && !metadata.replayed && !metadata.reset
      )
    }
    if (isTerminalStatus(metadata.status)) dispatch('checkStatus', runId)
  },

  /** The primary-backed saved outcome always wins over late live output. */
  applySnapshot({ state, commit, dispatch }, { runId, snapshot }) {
    const follower = state.followers[runId]
    if (
      !follower ||
      follower.finished ||
      runtime(this, runId).suspended ||
      !this.getters['auth/isAuthenticated']
    ) {
      return
    }
    const terminal = isTerminalStatus(snapshot.status)
    const type = this.$registry.get('chatRunType', follower.runType)
    if (!terminal) {
      commit('UPDATE_FOLLOWER', {
        runId,
        values: {
          view: {
            ...follower.view,
            status: snapshot.status,
            cancelRequested: Boolean(snapshot.cancel_requested_at),
          },
        },
      })
      return
    }
    const event = { kind: RUN_FINISHED, data: snapshot }
    commit('UPDATE_FOLLOWER', {
      runId,
      values: {
        finished: true,
        streaming: false,
        view: type.foldEvent(foldRunEvent(follower.view, event), event),
      },
    })
    stopRuntime(this, runId)
    type.onEvent(follower, event, false)
    dispatch('pruneFinished')
  },

  async checkStatus({ state, commit, dispatch }, runId) {
    const follower = state.followers[runId]
    const current = runtime(this, runId)
    if (
      !follower ||
      follower.finished ||
      follower.checkingStatus ||
      current.suspended ||
      !this.getters['auth/isAuthenticated']
    ) {
      return
    }
    const generation = current.generation
    const isCurrent = () =>
      state.followers[runId] === follower &&
      current.generation === generation &&
      !current.suspended &&
      this.getters['auth/isAuthenticated']
    commit('UPDATE_FOLLOWER', { runId, values: { checkingStatus: true } })
    try {
      const snapshot = await chatRunsService(this.$client).get(runId)
      if (!isCurrent()) return
      await dispatch('applySnapshot', { runId, snapshot })
      if (!follower.finished && !follower.streaming) dispatch('connect', runId)
    } catch (error) {
      if (!isCurrent()) return
      if ([401, 403, 404, 410].includes(error.response?.status)) {
        await dispatch('unavailable', runId)
      }
    } finally {
      if (isCurrent()) {
        commit('UPDATE_FOLLOWER', { runId, values: { checkingStatus: false } })
        scheduleStatus(this, runId)
      }
    }
  },

  /** Focus or a regained network permits another bounded attempt to stream. */
  resumeFollowers({ state, commit, dispatch }) {
    for (const { runId, finished, streaming } of Object.values(
      state.followers
    )) {
      if (finished) continue
      // Timers pause while a computer sleeps, so check the silence on waking.
      if (streaming) {
        restartIfSilent(this, runId)
        continue
      }
      commit('UPDATE_FOLLOWER', { runId, values: { reconnectAttempts: 0 } })
      dispatch('connect', runId)
    }
  },

  unavailable({ commit, dispatch }, runId) {
    stopRuntime(this, runId)
    commit('UPDATE_FOLLOWER', {
      runId,
      values: { finished: true, replayUnavailable: true, streaming: false },
    })
    dispatch('pruneFinished')
  },

  /** Lightweight discovery only: output always arrives through HTTP. */
  handleChanged({ state, dispatch }, { runId, runType, chatId }) {
    const follower = state.followers[runId]
    if (follower) {
      // An open stream brings the change itself, unless it lost the output.
      if (!follower.streaming || follower.replayUnavailable) {
        return dispatch('checkStatus', runId)
      }
      return
    }
    if (state.subscriptions[runType] === chatId) {
      return dispatch('follow', { runId, runType, chatId })
    }
  },

  /** Recover what a resubscription after a websocket reconnect may have missed. */
  handlePageAdd(
    { state, getters, dispatch },
    { run_type: runType, chat_id: chatId }
  ) {
    if (state.subscriptions[runType] !== Number(chatId)) return
    const socket = this.app.$realtime.socket
    if (sockets(this).get(runType) === socket) return
    sockets(this).set(runType, socket)
    for (const follower of getters.getFollowersOfChat(
      runType,
      Number(chatId)
    )) {
      if (!follower.finished && !follower.streaming) {
        dispatch('checkStatus', follower.runId)
      }
    }
    return this.$registry
      .get('chatRunType', runType)
      .refreshChat(Number(chatId))
  },

  async cancelRun({ state, commit, dispatch }, runId) {
    const follower = state.followers[runId]
    if (!follower || follower.finished || follower.stopRequested) return
    commit('UPDATE_FOLLOWER', { runId, values: { stopRequested: true } })
    try {
      await chatRunsService(this.$client).cancel(runId)
      // An open stream brings the cancellation and the end itself.
      if (!follower.streaming) await dispatch('checkStatus', runId)
    } catch (error) {
      commit('UPDATE_FOLLOWER', { runId, values: { stopRequested: false } })
      throw error
    }
  },

  disconnect({ state, commit }) {
    for (const runId of Object.keys(state.followers)) {
      const current = runtime(this, runId)
      current.generation += 1
      current.suspended = true
      stopRuntime(this, runId)
      commit('UPDATE_FOLLOWER', {
        runId,
        values: { streaming: false, checkingStatus: false },
      })
    }
  },

  /** Retain a small outcome cache; active runs and product handoffs stay owned. */
  pruneFinished({ state, commit }) {
    const finished = Object.values(state.followers).filter(
      (follower) =>
        follower.finished &&
        !this.$registry
          .get('chatRunType', follower.runType)
          .shouldRetainFollower(follower)
    )
    for (const follower of finished.slice(0, -MAX_FINISHED_FOLLOWERS)) {
      stopRuntime(this, follower.runId)
      runtimes.get(this).delete(follower.runId)
      commit('REMOVE_FOLLOWER', follower.runId)
    }
  },

  waitUntilFinished({ state }, runId) {
    return new Promise((resolve) => {
      const follower = state.followers[runId]
      if (!follower || follower.finished) return resolve()
      // Keep the object: pruning it from state in the same tick must not hide
      // its terminal transition from an already waiting caller.
      const unwatch = this.watch(
        () => follower.finished,
        (finished) => {
          if (finished) {
            unwatch()
            resolve()
          }
        }
      )
    })
  },
}

export const getters = {
  getFollower: (state) => (runId) => state.followers[runId] || null,
  getFollowersOfChat: (state) => (runType, chatId) =>
    Object.values(state.followers).filter(
      (follower) => follower.runType === runType && follower.chatId === chatId
    ),
}
export default { namespaced: true, state, mutations, actions, getters }
