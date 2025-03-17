import { isSecureURL } from '@baserow/modules/core/utils/string'
import { logoutAndRedirectToLogin } from '@baserow/modules/core/utils/auth'

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
    this.registerCoreEvents()
  }

  /**
   * Creates a new connection with to the web socket so that real time updates can be
   * received.
   */
  connect(reconnect = true, anonymous = false) {
    this.reconnect = reconnect
    this.anonymous = anonymous

    const jwtToken = this.context.store.getters['auth/token']
    const token = anonymous ? jwtToken || 'anonymous' : jwtToken

    // If the user is already connected to the web socket, we don't have to do
    // anything.
    if (this.connected) {
      return
    }

    // Stop connecting if we have already tried more than 10 times, if we do not have
    // an authentication token or if the server has already responded with a failed
    // authentication error and the token has not changed.
    if (
      this.attempts > 10 ||
      token === null ||
      (!this.authenticationSuccess && token === this.lastToken)
    ) {
      this.context.store.dispatch('toast/setFailedConnecting', true)
      return
    }

    this.lastToken = token

    // The web socket url is the same as the PUBLIC_BACKEND_URL apart from the
    // protocol.
    const rawUrl = this.context.app.$config.PUBLIC_BACKEND_URL
    const url = new URL(rawUrl)
    url.protocol = isSecureURL(rawUrl) ? 'wss:' : 'ws:'
    url.pathname = '/ws/core/'

    this.socket = new WebSocket(`${url}?jwt_token=${token}`)
    this.socket.onopen = () => {
      this.context.store.dispatch('toast/setConnecting', false)
      this.connected = true
      this.attempts = 0

      // If the client needs to be subscribed to a page we can do that directly
      // after connecting.
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

      if (
        Object.prototype.hasOwnProperty.call(data, 'type') &&
        Object.prototype.hasOwnProperty.call(this.events, data.type)
      ) {
        this.events[data.type](this.context, data)
      }
    }

    /**
     * When the connection closes we want to reconnect immediately because we don't
     * want to miss any important real time updates. After the first attempt we want to
     * delay retry with 5 seconds.
     */
    this.socket.onclose = () => {
      this.connected = false
      // By default the user not subscribed to a page a.k.a `null`, so if the current
      // page is already null we can mark it as subscribed.
      this.subscribedToPages = this.pages.length === 0
      this.delayedReconnect()
    }
  }

  /**
   * If reconnecting is enabled then a timeout is created that will try to connect
   * to the backend one more time.
   */
  delayedReconnect() {
    if (!this.reconnect) {
      return
    }

    this.attempts++
    this.context.store.dispatch('toast/setConnecting', true)

    this.reconnectTimeout = setTimeout(
      () => {
        this.connect(true, this.anonymous)
      },
      // After the first try, we want to try again every 5 seconds.
      this.attempts > 1 ? 5000 : 0
    )
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
    this.socket.send(
      JSON.stringify({
        remove_page: page,
        ...parameters,
      })
    )
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
    if (this.connected) {
      this.socket.close()
    }

    this.context.store.dispatch('toast/setConnecting', false)
    this.context.store.dispatch('toast/setFailedConnecting', false)
    clearTimeout(this.reconnectTimeout)
    this.reconnect = false
    this.attempts = 0
    this.connected = false
  }

  /**
   * Registers a new event with the event registry.
   */
  registerEvent(type, callback) {
    this.events[type] = callback
  }

  /**
   * Registers all the core event handlers, which is for the workspaces and applications.
   */
  registerCoreEvents() {
    // When the authentication is successful we want to store the web socket id in
    // auth store. Every AJAX request will include the web socket id as header, this
    // way the backend knows that this client does not has to receive the event
    // because we already know about the change.
    this.registerEvent('authentication', ({ store }, data) => {
      store.dispatch('auth/setWebSocketId', data.web_socket_id)

      // Store if the authentication was successful in order to prevent retries that
      // will fail.
      this.authenticationSuccess = data.success
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
        if (
          err.message !==
          `The type ${data.job.type} is not found under namespace job in the registry.`
        ) {
          throw err
        }
      }
    })
  }
}

export default function (context, inject) {
  inject('realtime', new RealTimeHandler(context))
}
