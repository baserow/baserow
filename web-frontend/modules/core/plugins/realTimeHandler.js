import { isSecureURL } from '@baserow/modules/core/utils/string'
import { logoutAndRedirectToLogin } from '@baserow/modules/core/utils/auth'
import { useRuntimeConfig } from '#imports'

const RECONNECT_BASE_DELAY = 1000
const RECONNECT_MAX_DELAY = 30000
const RECONNECT_MAX_ATTEMPTS = 10
const RECONNECT_JITTER = 1000

export class RealTimeHandler {
  constructor(context) {
    this.context = context
    this.socket = null
    this.connected = false
    this.reconnect = false
    this.anonymous = false
    this.reconnectTimeout = null
    this.attempts = 0
    this.events = {}
    this.pages = []
    this.subscribedToPages = true
    this.lastToken = null
    this.authenticationSuccess = true
    this.authResponseReceived = false
    this.unloading = false

    // Realtime-updates state. The frontend tracks the highest
    // `realtime_update_id` it has observed for the active workspace.
    // The web_socket_id is generated once and persists across reconnects —
    // the server uses it to exclude the client's own events from replay.
    this.lastSeenRealtimeUpdateId = null
    this.lastSeenWorkspaceId = null
    this.webSocketId = crypto.randomUUID()

    this.registerCoreEvents()

    this._onPageHide = () => {
      this.unloading = true
    }
    this._onVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        this.unloading = false
      }
      if (
        document.visibilityState === 'visible' &&
        !this.connected &&
        this.reconnect
      ) {
        clearTimeout(this.reconnectTimeout)
        this.attempts = 0
        this.context.store.dispatch('toast/setFailedConnecting', false)
        this.connect(true, this.anonymous)
      }
    }

    if (import.meta.client) {
      window.addEventListener('beforeunload', this._onPageHide)
      window.addEventListener('pagehide', this._onPageHide)
      document.addEventListener('visibilitychange', this._onVisibilityChange)

      // Re-subscribe when the active workspace changes.
      this.context.store.subscribe((mutation) => {
        if (mutation.type === 'workspace/SET_SELECTED') {
          this._onActiveWorkspaceChanged()
        }
      })
    }
  }

  /**
   * Creates a new connection with to the web socket so that real time updates can be
   * received.
   */
  connect(reconnect = true, anonymous = false) {
    if (!import.meta.client) {
      return
    }

    this.reconnect = reconnect
    this.anonymous = anonymous

    const jwtToken = this.context.store.getters['auth/token']
    const token = anonymous ? jwtToken || 'anonymous' : jwtToken

    if (
      this.socket &&
      (this.socket.readyState === WebSocket.CONNECTING ||
        this.socket.readyState === WebSocket.OPEN)
    ) {
      return
    }

    if (this.socket) {
      this.socket.onclose = null
      this.socket = null
    }

    const maxAttemptsReached = this.attempts >= RECONNECT_MAX_ATTEMPTS
    const noToken = !token
    const tokenAlreadyRejected =
      this.authResponseReceived &&
      !this.authenticationSuccess &&
      this.lastToken === token
    if (maxAttemptsReached || noToken || tokenAlreadyRejected) {
      this.context.store.dispatch('toast/setFailedConnecting', true)
      this.context.store.dispatch('toast/setReconnecting', false)
      return
    }

    this.lastToken = token
    this.authResponseReceived = false

    // The web socket url is the same as the PUBLIC_BACKEND_URL apart from the
    // protocol.
    const config = useRuntimeConfig()
    const rawUrl = config.public.publicBackendUrl
    const url = new URL(rawUrl)
    url.protocol = isSecureURL(rawUrl) ? 'wss:' : 'ws:'
    url.pathname = '/ws/core/'

    this.socket = new WebSocket(
      `${url}?jwt_token=${token}&web_socket_id=${this.webSocketId}`
    )
    this.socket.onopen = () => {
      this.connected = true
      this.attempts = 0
      this.authenticationSuccess = true

      this.context.store.dispatch('toast/setFailedConnecting', false)
      this.context.store.dispatch('toast/setReconnecting', false)

      if (!this.subscribedToPages) {
        this.subscribeToPages()
      }
    }

    /**
     * The received messages are always JSON so we need to the parse it, extract the
     * type and call the correct event.
     */
    this.socket.onmessage = (message) => {
      let data = {}

      try {
        data = JSON.parse(message.data)
      } catch {
        return
      }

      this.updateLastSeenId(data)

      if (
        Object.prototype.hasOwnProperty.call(data, 'type') &&
        Object.prototype.hasOwnProperty.call(this.events, data.type)
      ) {
        for (const callback of this.events[data.type]) {
          callback(this.context, data)
        }
      }
    }

    this.socket.onclose = () => {
      this.connected = false
      // By default the user not subscribed to a page a.k.a `null`, so if the current
      // page is already null we can mark it as subscribed.
      this.subscribedToPages = this.pages.length === 0
      this.delayedReconnect()
    }
  }

  /**
   * Schedules a reconnection attempt with exponential backoff and jitter.
   */
  delayedReconnect() {
    if (!this.reconnect || this.unloading) {
      return
    }

    clearTimeout(this.reconnectTimeout)
    this.attempts++
    this.context.store.dispatch('toast/setReconnecting', true)

    const delay = Math.min(
      RECONNECT_BASE_DELAY * Math.pow(2, this.attempts - 1) +
        Math.floor(Math.random() * RECONNECT_JITTER),
      RECONNECT_MAX_DELAY
    )

    this.reconnectTimeout = setTimeout(() => {
      this.connect(true, this.anonymous)
    }, delay)
  }

  /**
   * Subscribes the client to a given page. After subscribing the client will
   * receive updated related to that page. This is for example used when a user
   * opens a table page.
   */
  subscribe(page, parameters) {
    const pageScope = {
      page,
      parameters,
    }

    if (
      !this.pages.some(
        (elem) => JSON.stringify(elem) === JSON.stringify(pageScope)
      )
    ) {
      this.pages.push(pageScope)
      // If the client is already connected we can
      // subscribe to updates for all pages.
      if (this.connected) {
        this.subscribeToPage(page, parameters)
      } else {
        this.subscribedToPages = false
      }
    }
  }

  /**
   * Unsubscribes the client from a given page. The client will
   * stop receiving updates related to that page.
   */
  unsubscribe(page, parameters) {
    this.pages = this.pages.filter(
      (item) => JSON.stringify(item) !== JSON.stringify({ page, parameters })
    )
    if (this.connected) {
      this.socket.send(
        JSON.stringify({
          remove_page: page,
          ...parameters,
        })
      )
    }
  }

  /*
   * Subscribes the client to a new page if the client is
   * connected.
   */
  subscribeToPage(page, parameters) {
    if (this.connected) {
      this.socket.send(
        JSON.stringify({
          page: page === null ? '' : page,
          ...parameters,
        })
      )
    }
  }

  /**
   * Requests real time updates for the list of pages that
   * have been collected by the subscribe() call.
   */
  subscribeToPages() {
    if (this.subscribedToPages) {
      return
    }

    for (const { page, parameters } of this.pages) {
      this.subscribeToPage(page, parameters)
    }

    this.subscribedToPages = true
  }

  /**
   * Disconnects the socket and resets all the variables. The can be used when
   * navigating to another page that doesn't require updates.
   */
  disconnect() {
    if (this.socket) {
      this.socket.onclose = null
      this.socket.close()
      this.socket = null
    }

    this.context.store.dispatch('toast/setFailedConnecting', false)
    this.context.store.dispatch('toast/setReconnecting', false)
    this.context.store.dispatch('toast/setWorkspaceStale', false)
    clearTimeout(this.reconnectTimeout)
    this.reconnect = false
    this.attempts = 0
    this.connected = false
    this.lastSeenRealtimeUpdateId = null
    this.lastSeenWorkspaceId = null
  }

  /**
   * Returns the id of the currently active workspace, or null if no workspace
   * is selected.
   */
  _getActiveWorkspaceId() {
    const workspace = this.context.store.getters['workspace/getSelected']
    if (!workspace || !workspace.id) return null
    return workspace.id
  }

  /**
   * Sends ``realtime_subscribe`` for the currently active workspace.
   * On initial connect ``last_seen_id`` is null, asking the server only for
   * a baseline. On reconnect it is populated so the server can answer
   * whether anything new happened while we were offline.
   */
  _sendRealtimeSubscribe(workspaceId) {
    if (
      !this.socket ||
      this.socket.readyState !== WebSocket.OPEN ||
      !workspaceId
    ) {
      return
    }
    const isSameWorkspace = this.lastSeenWorkspaceId === workspaceId
    const lastSeenId = isSameWorkspace ? this.lastSeenRealtimeUpdateId : null
    this.lastSeenWorkspaceId = workspaceId
    this.socket.send(
      JSON.stringify({
        type: 'realtime_subscribe',
        workspace_id: workspaceId,
        last_seen_id: lastSeenId,
      })
    )
  }

  _onActiveWorkspaceChanged() {
    // Switching workspaces re-baselines: the new workspace has its own id
    // space so we drop the cached high-water mark. Any pending "workspace
    // stale" toast belonged to the previous workspace and is irrelevant in
    // the new context.
    const newWorkspaceId = this._getActiveWorkspaceId()
    if (newWorkspaceId === this.lastSeenWorkspaceId) {
      return
    }
    this.lastSeenRealtimeUpdateId = null
    this.lastSeenWorkspaceId = null
    this.context.store.dispatch('toast/setWorkspaceStale', false)
    this._sendRealtimeSubscribe(newWorkspaceId)
  }

  updateLastSeenId(data) {
    if (
      data &&
      typeof data === 'object' &&
      typeof data.realtime_update_id === 'number'
    ) {
      const current = this.lastSeenRealtimeUpdateId
      if (current === null || data.realtime_update_id > current) {
        this.lastSeenRealtimeUpdateId = data.realtime_update_id
      }
    }
  }

  /**
   * Registers a new event with the event registry.
   */
  registerEvent(type, callback) {
    if (!this.events[type]) {
      this.events[type] = []
    }
    this.events[type].push(callback)
  }

  /**
   * Registers all the core event handlers, which is for the workspaces and applications.
   */
  registerCoreEvents() {
    // web_socket_id is stored in auth so every AJAX request includes it as a
    // header — the backend uses it to skip echoing the event back to the
    // originating client.
    this.registerEvent('authentication', ({ store }, data) => {
      store.dispatch('auth/setWebSocketId', this.webSocketId)

      this.authenticationSuccess = data.success
      this.authResponseReceived = true

      if (data.success) {
        const workspaceId = this._getActiveWorkspaceId()
        if (workspaceId) {
          this._sendRealtimeSubscribe(workspaceId)
        }
      }
    })

    this.registerEvent('realtime_subscribe_result', ({ store }, data) => {
      // Ignore results for a workspace that is no longer active (the user
      // may have switched workspaces while the response was in flight).
      if (data.workspace_id !== this._getActiveWorkspaceId()) {
        return
      }
      const previous = this.lastSeenRealtimeUpdateId
      const showToast =
        data.stale &&
        typeof data.current_latest_id === 'number' &&
        (previous === null || data.current_latest_id > previous)
      this.lastSeenRealtimeUpdateId = Math.max(
        data.current_latest_id,
        previous ?? 0
      )
      if (showToast) {
        store.dispatch('toast/setWorkspaceStale', true)
      }
    })

    this.registerEvent('user_data_updated', ({ store }, data) => {
      store.dispatch('auth/forceUpdateUserData', data.user_data)
    })

    this.registerEvent('user_updated', ({ store }, data) => {
      store.dispatch('workspace/forceUpdateWorkspaceUserAttributes', {
        userId: data.user.id,
        values: {
          name: data.user.first_name,
        },
      })
    })

    this.registerEvent('user_deleted', ({ store }, data) => {
      store.dispatch('workspace/forceUpdateWorkspaceUserAttributes', {
        userId: data.user.id,
        values: {
          to_be_deleted: true,
        },
      })
    })

    this.registerEvent('user_restored', ({ store }, data) => {
      store.dispatch('workspace/forceUpdateWorkspaceUserAttributes', {
        userId: data.user.id,
        values: {
          to_be_deleted: false,
        },
      })
    })

    this.registerEvent('user_permanently_deleted', ({ store }, data) => {
      store.dispatch('workspace/forceDeleteUser', {
        userId: data.user_id,
      })
    })

    this.registerEvent('group_created', ({ store }, data) => {
      store.dispatch('workspace/forceCreate', data.workspace)
    })

    this.registerEvent('group_restored', ({ store }, data) => {
      store.dispatch('workspace/forceCreate', data.workspace)
      store.dispatch('application/forceCreateAll', data.applications)
    })

    this.registerEvent('group_updated', ({ store }, data) => {
      const workspace = store.getters['workspace/get'](data.workspace_id)
      if (workspace !== undefined) {
        store.dispatch('workspace/forceUpdate', {
          workspace,
          values: data.workspace,
        })
      }
    })

    this.registerEvent('group_deleted', ({ store }, data) => {
      const workspace = store.getters['workspace/get'](data.workspace_id)
      if (workspace !== undefined) {
        store.dispatch('workspace/forceDelete', workspace)
      }
    })

    this.registerEvent('groups_reordered', ({ store }, data) => {
      store.dispatch('workspace/forceOrder', data.workspace_ids)
    })

    this.registerEvent('group_user_added', ({ store }, data) => {
      store.dispatch('workspace/forceAddWorkspaceUser', {
        workspaceId: data.workspace_id,
        values: data.workspace_user,
      })
    })

    this.registerEvent('group_user_updated', ({ store }, data) => {
      store.dispatch('workspace/forceUpdateWorkspaceUser', {
        id: data.id,
        workspaceId: data.workspace_id,
        values: data.workspace_user,
      })
    })

    this.registerEvent('group_user_deleted', ({ store }, data) => {
      store.dispatch('workspace/forceDeleteWorkspaceUser', {
        id: data.id,
        workspaceId: data.workspace_id,
        values: data.workspace_user,
      })
    })

    this.registerEvent('application_created', ({ store }, data) => {
      store.dispatch('application/forceCreate', data.application)
    })

    this.registerEvent('application_updated', ({ store }, data) => {
      const application = store.getters['application/get'](data.application_id)
      if (application !== undefined) {
        store.dispatch('application/forceUpdate', {
          application,
          data: data.application,
        })
      }
    })

    this.registerEvent('application_deleted', ({ store }, data) => {
      const application = store.getters['application/get'](data.application_id)
      if (application !== undefined) {
        store.dispatch('application/forceDelete', application)
      }
    })

    this.registerEvent('applications_reordered', ({ store }, data) => {
      const workspace = store.getters['workspace/get'](data.workspace_id)
      if (workspace !== undefined) {
        store.commit('application/ORDER_ITEMS', {
          workspace,
          order: data.order,
          isHashed: true,
        })
      }
    })

    // invitations
    this.registerEvent(
      'workspace_invitation_updated_or_created',
      ({ store }, data) => {
        store.dispatch(
          'auth/forceUpdateOrCreateWorkspaceInvitation',
          data.invitation
        )
      }
    )

    this.registerEvent('workspace_invitation_accepted', ({ store }, data) => {
      store.dispatch('auth/forceAcceptWorkspaceInvitation', data.invitation)
    })

    this.registerEvent('workspace_invitation_rejected', ({ store }, data) => {
      store.dispatch('auth/forceRejectWorkspaceInvitation', data.invitation)
    })

    // notifications
    this.registerEvent('notifications_created', ({ store }, data) => {
      store.dispatch('notification/forceCreateInBulk', {
        notifications: data.notifications,
      })
    })

    this.registerEvent('notifications_fetch_required', ({ store }, data) => {
      store.dispatch('notification/forceRefetch', {
        notificationsAdded: data.notifications_added,
      })
    })

    this.registerEvent('notification_marked_as_read', ({ store }, data) => {
      store.dispatch('notification/forceMarkAsRead', {
        notification: data.notification,
      })
    })

    this.registerEvent('all_notifications_marked_as_read', ({ store }) => {
      store.dispatch('notification/forceMarkAllAsRead')
    })

    this.registerEvent('all_notifications_cleared', ({ store }) => {
      store.dispatch('notification/forceClearAll')
    })

    this.registerEvent('force_disconnect', ({ store }) => {
      this.reconnect = false
      logoutAndRedirectToLogin(this.context.app.router, store, false, true)
    })

    this.registerEvent('job_started', ({ store }, data) => {
      try {
        store.dispatch('job/create', data.job)
      } catch (err) {
        // TODO: some job types have no frontend handlers (JobType subclasses)
        //  registered. This will cause an error during creation. The proper fix
        //  would be to add missing JobTypes.
        // Check if the error is about a missing job type in the registry
        const missingTypePattern = new RegExp(
          `^The type "${data.job.type}" is not found under namespace "job" in the registry\\.`
        )
        if (!missingTypePattern.test(err.message)) {
          throw err
        }
      }
    })
  }
}

export default defineNuxtPlugin({
  name: 'realtime',
  dependsOn: ['store', 'registry'],
  setup(nuxtApp) {
    const context = {
      store: nuxtApp.$store,
      app: nuxtApp,
    }

    nuxtApp.provide('realtime', new RealTimeHandler(context))
  },
})
