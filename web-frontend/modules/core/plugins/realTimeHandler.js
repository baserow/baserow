import { isSecureURL } from '@baserow/modules/core/utils/string'
import { logoutAndRedirectToLogin } from '@baserow/modules/core/utils/auth'
import { FIRST_CONNECT_CURSOR } from '@baserow/modules/core/plugins/realtimeProtocol'
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

    this.lastSeenEventId = FIRST_CONNECT_CURSOR
    this.replayEnabled = false

    this.registerCoreEvents()

    this._onPageHide = () => {
      this.unloading = true
    }
    // Immediate retry on tab refocus or network restoration.
    this._onShouldRetryNow = () => {
      if (!this.connected && this.reconnect) {
        this._retryReconnectNow()
      }
    }
    this._onVisibilityChange = () => {
      if (!this._isDocumentVisible()) {
        return
      }
      this.unloading = false
      this._onShouldRetryNow()
    }

    if (import.meta.client) {
      window.addEventListener('beforeunload', this._onPageHide)
      window.addEventListener('pagehide', this._onPageHide)
      document.addEventListener('visibilitychange', this._onVisibilityChange)
      window.addEventListener('online', this._onShouldRetryNow)
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

    // "Failed — refresh" is only for genuine auth problems; transient
    // network failures keep retrying with capped backoff.
    const noToken = !token
    const tokenAlreadyRejected =
      this.authResponseReceived &&
      !this.authenticationSuccess &&
      this.lastToken === token
    if (noToken || tokenAlreadyRejected) {
      if (!this._isDocumentHidden()) {
        this.context.store.dispatch('toast/setFailedConnecting', true)
      }
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
    const webSocketId = this.context.store.getters['auth/webSocketId']

    this.socket = new WebSocket(
      `${url}?jwt_token=${token}&web_socket_id=${webSocketId}`
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
      // Surface the disconnect immediately — the toast persists through the
      // hidden/offline wait and through retry attempts until ``onopen`` runs.
      if (this.reconnect) {
        this.context.store.dispatch('toast/setReconnecting', true)
      }
      this.subscribedToPages = this.pages.length === 0
      this.delayedReconnect()
    }
  }

  /**
   * Schedules a reconnection attempt with exponential backoff and jitter.
   * Bails when the tab is hidden or the navigator is offline; the
   * ``visibilitychange`` / ``online`` handlers resume via
   * ``_retryReconnectNow`` the moment either clears.
   */
  delayedReconnect() {
    if (
      !this.reconnect ||
      this.unloading ||
      this._isDocumentHidden() ||
      !this._isNavigatorOnline()
    ) {
      return
    }

    clearTimeout(this.reconnectTimeout)
    this.attempts++
    this.context.store.dispatch('toast/setReconnecting', true)

    // Cap the exponent so retries past the threshold stay at
    // ``RECONNECT_MAX_DELAY`` instead of computing huge values.
    const exponent = Math.min(this.attempts, RECONNECT_MAX_ATTEMPTS) - 1
    const delay = Math.min(
      RECONNECT_BASE_DELAY * Math.pow(2, exponent) +
        Math.floor(Math.random() * RECONNECT_JITTER),
      RECONNECT_MAX_DELAY
    )

    this.reconnectTimeout = setTimeout(() => {
      this.connect(true, this.anonymous)
    }, delay)
  }

  _isDocumentVisible() {
    return (
      typeof document !== 'undefined' && document.visibilityState === 'visible'
    )
  }

  _isDocumentHidden() {
    return (
      typeof document !== 'undefined' && document.visibilityState === 'hidden'
    )
  }

  _isNavigatorOnline() {
    // ``navigator.onLine === false`` is the only reliable signal.
    return typeof navigator === 'undefined' || navigator.onLine !== false
  }

  _retryReconnectNow() {
    clearTimeout(this.reconnectTimeout)
    this.attempts = 0
    this.context.store.dispatch('toast/setFailedConnecting', false)
    // Keep the "Reconnecting" toast up until ``onopen`` clears it; flickering
    // it off here just confuses the user during the retry round-trip.
    this.connect(true, this.anonymous)
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
    this.context.store.dispatch('toast/setWorkspaceOutdated', false)
    clearTimeout(this.reconnectTimeout)
    this.reconnect = false
    this.attempts = 0
    this.connected = false
    this.lastSeenEventId = FIRST_CONNECT_CURSOR
    // Reset until the next auth message confirms replay is enabled.
    this.replayEnabled = false
  }

  /**
   * Sends ``replay_events`` when replay is enabled. The cursor is
   * FIRST_CONNECT_CURSOR (fresh session), NO_REPLAY_AVAILABLE (reconnect
   * without a high-water mark), or the highest ``_event_id`` seen so far.
   */
  _sendReplayEventsRequest() {
    if (!this.replayEnabled) {
      return
    }
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return
    }
    this.socket.send(
      JSON.stringify({
        type: 'replay_events',
        last_seen_id: this.lastSeenEventId,
      })
    )
  }

  updateLastSeenId(data) {
    if (
      data &&
      typeof data === 'object' &&
      typeof data._event_id === 'number' &&
      data._event_id > this.lastSeenEventId
    ) {
      this.lastSeenEventId = data._event_id
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
    this.registerEvent('authentication', ({ store }, data) => {
      this.authenticationSuccess = data.success
      this.authResponseReceived = true
      this.replayEnabled = data.replay_enabled === true

      if (data.success) {
        this._sendReplayEventsRequest()
      }
    })

    this.registerEvent('replay_events_result', ({ store }, data) => {
      const latestEventId = data.latest_event_id
      if (!data.force_refresh && typeof latestEventId === 'number') {
        // ``latest_event_id`` can be NO_REPLAY_AVAILABLE (0) when the
        // server has no events recorded yet; store it verbatim.
        this.lastSeenEventId = Math.max(latestEventId, this.lastSeenEventId)
      }
      store.dispatch('toast/setWorkspaceOutdated', data.force_refresh === true)
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
