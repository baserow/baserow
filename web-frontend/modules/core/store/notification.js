import notificationService from '@baserow/modules/core/services/notification'

export const state = () => ({
  currentWorkspaceId: null,
  loading: false,
  loaded: false,
  userUnreadCount: 0,
  perWorkspaceUnreadCount: {},
  anyOtherWorkspaceWithUnread: false,
  totalCount: 0,
  currentCount: 0,
  items: [],
})

function anyUnreadInOtherWorkspaces(state) {
  return Object.entries(state.perWorkspaceUnreadCount).some(
    ([workspaceId, count]) =>
      state.currentWorkspaceId !== parseInt(workspaceId) && count > 0
  )
}

export const mutations = {
  SET_WORKSPACE(state, workspace) {
    const workspaceChanged = state.currentWorkspaceId !== workspace.id
    state.currentWorkspaceId = workspace.id
    state.anyOtherWorkspaceWithUnread = anyUnreadInOtherWorkspaces(state)
    if (workspaceChanged) {
      state.loaded = false
    }
  },
  SET_USER_UNREAD_COUNT(state, count) {
    state.userUnreadCount = count || 0
  },
  SET(state, { notifications, totalCount = undefined }) {
    state.items = notifications
    state.currentCount = notifications.length
    state.totalCount = totalCount || notifications.length
  },
  ADD_NOTIFICATIONS(state, { notifications, totalCount }) {
    notifications.reverse().forEach((notification) => {
      const existingIndex = state.items.findIndex(
        (c) => c.id === notification.id
      )
      if (existingIndex >= 0) {
        // Prevent duplicates by just replacing them inline
        state.items.splice(existingIndex, 0, notification)
      } else {
        state.items.unshift(notification)
      }
    })
    state.currentCount = state.items.length
    state.totalCount = totalCount
  },
  SET_NOTIFICATIONS_READ(
    state,
    { notificationIds, value, setUserCount, setWorkspaceCount }
  ) {
    const updateCount = value
      ? (curr, count = 1) => (curr > count ? curr - count : 0)
      : (curr, count = 1) => (curr || 0) + count

    for (const item of state.items) {
      if (item.read === value || !notificationIds.includes(item.id)) {
        continue
      }

      item.read = value

      const workspaceId = item.workspace?.id
      if (workspaceId) {
        const currCount = state.perWorkspaceUnreadCount[workspaceId] || 0
        state.perWorkspaceUnreadCount[workspaceId] = updateCount(currCount)
      } else {
        state.userUnreadCount = updateCount(state.userUnreadCount)
      }
    }

    if (setUserCount !== undefined) {
      state.userUnreadCount = setUserCount
    }

    if (setWorkspaceCount !== undefined) {
      state.perWorkspaceUnreadCount[state.currentWorkspaceId] =
        setWorkspaceCount
    }
  },
  SET_LOADING(state, loading) {
    state.loading = loading
  },
  SET_LOADED(state, loaded) {
    state.loaded = loaded
  },
  SET_TOTAL_COUNT(state, totalCount) {
    state.totalCount = totalCount
  },
  SET_PER_WORKSPACE_UNREAD_COUNT(state, perWorkspaceUnreadCount) {
    state.perWorkspaceUnreadCount = perWorkspaceUnreadCount
    state.anyOtherWorkspaceWithUnread = anyUnreadInOtherWorkspaces(state)
  },
  INCREMENT_WORKSPACE_UNREAD_COUNT(
    state,
    workspaceCount = { workspaceId: null, count: 1 }
  ) {
    const { workspaceId, count } = workspaceCount
    if (!workspaceId) {
      return
    }

    const currentCount = state.perWorkspaceUnreadCount[workspaceId] || 0
    state.perWorkspaceUnreadCount[workspaceId] = currentCount + count
    state.anyOtherWorkspaceWithUnread = anyUnreadInOtherWorkspaces(state)
  },
  SET_WORKSPACE_UNREAD_COUNT(state, { workspaceId, count }) {
    state.perWorkspaceUnreadCount[workspaceId] = count
    state.anyOtherWorkspaceWithUnread = anyUnreadInOtherWorkspaces(state)
  },
  SET_UNREAD_COUNT(state, { userCount, currentWorkspaceUnreadCount }) {
    state.userUnreadCount = userCount
    state.perWorkspaceUnreadCount[state.currentWorkspaceId] =
      currentWorkspaceUnreadCount
  },
  UPDATE_UNREAD_COUNTS(state, { notificationsAdded }) {
    for (const addedCount of notificationsAdded) {
      const workspaceId = addedCount.workspace_id
      const count = addedCount.count
      if (workspaceId === null) {
        state.userUnreadCount = (state.userUnreadCount || 0) + addedCount.count
      } else {
        const currentCount = state.perWorkspaceUnreadCount[workspaceId] || 0
        state.perWorkspaceUnreadCount[workspaceId] = currentCount + count
      }
    }
    state.anyOtherWorkspaceWithUnread = anyUnreadInOtherWorkspaces(state)
  },
}

export const actions = {
  /**
   * Fetches the next 20 notifications from the server and adds them to the comments list.
   */
  async fetchNextSetOfNotifications({ commit, state }) {
    const { $registry, $i18n, $client, $config } = this
    commit('SET_LOADING', true)
    try {
      // We have to use offset based paging here as new notifications can be added by the
      // user or come in via realtime events.
      const { data } = await notificationService($client).fetchAll(
        state.currentWorkspaceId,
        { offset: state.currentCount }
      )
      commit('ADD_NOTIFICATIONS', {
        notifications: data.results,
        totalCount: data.count,
      })
    } finally {
      commit('SET_LOADING', false)
    }
  },
  async fetchAll({ commit, state }, { workspaceId }) {
    const { $registry, $i18n, $client, $config } = this
    commit('SET_LOADED', false)
    commit('SET_LOADING', true)
    try {
      const { data } = await notificationService($client).fetchAll(
        workspaceId,
        {}
      )
      commit('SET', { notifications: data.results, totalCount: data.count })
      commit('SET_LOADED', true)
    } catch (error) {
      commit('SET', { notifications: [] })
      throw error
    } finally {
      commit('SET_LOADING', false)
    }
    return state.items
  },
  async clearAll({ commit, state }) {
    const { $registry, $i18n, $client, $config } = this

    const notifications = state.items
    const totalCount = state.totalCount
    const prevUserCount = state.userUnreadCount
    const prevWorkspaceCount =
      state.perWorkspaceUnreadCount[state.currentWorkspaceId]
    commit('SET', { notifications: [] })
    commit('SET_UNREAD_COUNT', {
      userCount: 0,
      currentWorkspaceUnreadCount: 0,
    })
    try {
      await notificationService($client).clearAll(state.currentWorkspaceId)
    } catch (error) {
      commit('SET', { notifications, totalCount })
      commit('SET_UNREAD_COUNT', {
        userCount: prevUserCount,
        currentWorkspaceUnreadCount: prevWorkspaceCount,
      })
      throw error
    }
  },
  forceClearAll({ commit }) {
    commit('SET', { notifications: [] })
    commit('SET_UNREAD_COUNT', {
      userCount: 0,
      currentWorkspaceUnreadCount: 0,
    })
  },
  reset({ commit, dispatch }) {
    dispatch('forceClearAll')
    commit('SET_LOADED', false)
  },
  async markAsRead({ commit, state }, { notification }) {
    const { $registry, $i18n, $client, $config } = this

    commit('SET_NOTIFICATIONS_READ', {
      notificationIds: [notification.id],
      value: true,
    })
    try {
      await notificationService($client).markAsRead(
        state.currentWorkspaceId,
        notification.id
      )
    } catch (error) {
      commit('SET_NOTIFICATIONS_READ', {
        notificationIds: [notification.id],
        value: false,
      })
      throw error
    }
  },
  forceMarkAsRead({ commit, state }, { notification }) {
    commit('SET_NOTIFICATIONS_READ', {
      notificationIds: [notification.id],
      value: true,
    })
  },
  forceRefetch({ commit, state }, { notificationsAdded }) {
    commit('UPDATE_UNREAD_COUNTS', { notificationsAdded })
    commit('SET_LOADED', false)
  },
  async markAllAsRead({ commit, state }) {
    const { $registry, $i18n, $client, $config } = this
    const notificationIds = state.items
      .filter((notification) => !notification.read)
      .map((notification) => notification.id)

    const prevUserCount = state.userUnreadCount
    const prevWorkspaceCount =
      state.perWorkspaceUnreadCount[state.currentWorkspaceId]

    commit('SET_NOTIFICATIONS_READ', {
      notificationIds,
      value: true,
      setUserCount: 0,
      setWorkspaceCount: 0,
    })
    try {
      await notificationService($client).markAllAsRead(state.currentWorkspaceId)
    } catch (error) {
      commit('SET_NOTIFICATIONS_READ', {
        notificationIds,
        value: false,
        setUserCount: prevUserCount,
        setWorkspaceCount: prevWorkspaceCount,
      })
      throw error
    }
  },
  forceMarkAllAsRead({ commit, state }) {
    const notificationIds = state.items
      .filter((notification) => !notification.read)
      .map((notification) => notification.id)
    commit('SET_NOTIFICATIONS_READ', {
      notificationIds,
      value: true,
      setUserCount: 0,
      setWorkspaceCount: 0,
    })
  },
  forceCreateInBulk({ commit, state }, { notifications }) {
    const unreadCountPerWorkspace = notifications.reduce(
      (acc, notification) => {
        if (!notification.read) {
          const workspaceId = notification.workspace?.id || 'null'
          acc[workspaceId] = acc[workspaceId] ? acc[workspaceId] + 1 : 1
        }
        return acc
      },
      {}
    )
    const notificationsAdded = Object.entries(unreadCountPerWorkspace).map(
      ([workspaceId, count]) => ({
        workspace_id: workspaceId !== 'null' ? parseInt(workspaceId) : null,
        count,
      })
    )
    commit('UPDATE_UNREAD_COUNTS', { notificationsAdded })

    const visibleNotifications = notifications.filter(
      (n) => !n.workspace?.id || n.workspace?.id === state.currentWorkspaceId
    )
    if (visibleNotifications.length > 0) {
      commit('ADD_NOTIFICATIONS', {
        notifications: visibleNotifications,
        totalCount: state.totalCount + visibleNotifications.length,
      })
    }
  },
  setWorkspace({ commit }, { workspace }) {
    commit('SET_WORKSPACE', workspace)
  },
  setPerWorkspaceUnreadCount({ commit }, { workspaces }) {
    commit(
      'SET_PER_WORKSPACE_UNREAD_COUNT',
      Object.fromEntries(
        workspaces.map((wp) => [wp.id, wp.unread_notifications_count])
      )
    )
  },
  setUserUnreadCount({ commit }, { count }) {
    commit('SET_USER_UNREAD_COUNT', count)
  },
}

export const getters = {
  getWorkspaceId(state) {
    return state.currentWorkspaceId
  },
  getAll(state) {
    return state.items
  },
  getUnreadCount(state) {
    const workspaceCount =
      state.perWorkspaceUnreadCount[state.currentWorkspaceId] || 0
    return state.userUnreadCount + workspaceCount
  },
  getCurrentCount(state) {
    return state.currentCount
  },
  getTotalCount(state) {
    return state.totalCount
  },
  getLoading(state) {
    return state.loading
  },
  getLoaded(state) {
    return state.loaded
  },
  userHasUnread(state) {
    return state.userUnreadCount > 0
  },
  workspaceHasUnread: (state) => (workspaceId) => {
    return (state.perWorkspaceUnreadCount[workspaceId] || 0) > 0
  },
  anyOtherWorkspaceWithUnread(state) {
    return state.anyOtherWorkspaceWithUnread
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
