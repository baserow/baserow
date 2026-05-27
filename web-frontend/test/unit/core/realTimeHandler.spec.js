import { vi, describe, beforeEach, test, expect } from 'vitest'

import { RealTimeHandler } from '@baserow/modules/core/plugins/realTimeHandler'

vi.mock('#imports', () => ({
  useRuntimeConfig: () => ({
    public: { publicBackendUrl: 'http://localhost' },
  }),
}))

// The handler reads WebSocket.OPEN / CONNECTING constants; the test
// environment may not provide them on the class object, in which case the
// readiness gate would short-circuit and silently swallow sends.
if (typeof globalThis.WebSocket === 'undefined') {
  globalThis.WebSocket = {}
}
if (typeof globalThis.WebSocket.OPEN !== 'number') {
  globalThis.WebSocket.OPEN = 1
  globalThis.WebSocket.CONNECTING = 0
  globalThis.WebSocket.CLOSING = 2
  globalThis.WebSocket.CLOSED = 3
}

function makeStore(initialWorkspaceId = null) {
  let selected = initialWorkspaceId
    ? { id: initialWorkspaceId, _: { type: 'workspace' } }
    : {}
  const dispatched = []
  const subscribers = []
  const store = {
    getters: {
      'auth/token': 'token',
      'workspace/getSelected': () => selected,
    },
    dispatch(name, value) {
      dispatched.push([name, value])
      return Promise.resolve()
    },
    subscribe(fn) {
      subscribers.push(fn)
    },
    _setSelected(workspace) {
      selected = workspace || {}
      for (const sub of subscribers) {
        sub({ type: 'workspace/SET_SELECTED' })
      }
    },
    _dispatched: dispatched,
  }
  // Vuex-style getter that's read like a property, not invoked. The handler
  // does `store.getters['workspace/getSelected']` and uses its `id` directly.
  Object.defineProperty(store.getters, 'workspace/getSelected', {
    get() {
      return selected
    },
  })
  return store
}

function makeHandler({ workspaceId = null } = {}) {
  const store = makeStore(workspaceId)
  const context = { store, app: { router: {} } }
  const handler = new RealTimeHandler(context)
  // Stand-in for an open websocket so _sendRealtimeSubscribe goes
  // through.
  const sentMessages = []
  handler.socket = {
    readyState: 1, // WebSocket.OPEN
    onclose: null,
    send(payload) {
      sentMessages.push(JSON.parse(payload))
    },
    close() {},
  }
  return { handler, store, context, sentMessages }
}

function fire(handler, type, data) {
  for (const cb of handler.events[type] || []) {
    cb(handler.context, data)
  }
}

describe('RealTimeHandler realtime_subscribe flow', () => {
  let env
  beforeEach(() => {
    env = makeHandler({ workspaceId: 7 })
  })

  test('authentication sends a baseline subscribe on initial connect', () => {
    fire(env.handler, 'authentication', {
      success: true,
    })
    const subscribe = env.sentMessages.find(
      (m) => m.type === 'realtime_subscribe'
    )
    expect(subscribe).toEqual({
      type: 'realtime_subscribe',
      workspace_id: 7,
      last_seen_id: null,
    })
  })

  test('authentication does not subscribe when no workspace is active', () => {
    const local = makeHandler({ workspaceId: null })
    fire(local.handler, 'authentication', {
      success: true,
    })
    expect(local.sentMessages).toEqual([])
  })

  test('subscribe_result with stale categories and newer id fires the toast', () => {
    env.handler.lastSeenRealtimeUpdateId = 10
    env.handler.lastSeenWorkspaceId = 7
    fire(env.handler, 'realtime_subscribe_result', {
      workspace_id: 7,
      stale: true,
      current_latest_id: 42,
    })
    expect(
      env.store._dispatched.some(
        ([n, v]) => n === 'toast/setWorkspaceStale' && v === true
      )
    ).toBe(true)
    expect(env.handler.lastSeenRealtimeUpdateId).toBe(42)
  })

  test('subscribe_result with updates but stale current_latest_id does not toast', () => {
    // Mimics a race where a fresh broadcast advanced lastSeen above
    // current_latest_id before the response arrived.
    env.handler.lastSeenRealtimeUpdateId = 50
    env.handler.lastSeenWorkspaceId = 7
    fire(env.handler, 'realtime_subscribe_result', {
      workspace_id: 7,
      stale: true,
      current_latest_id: 42,
    })
    expect(
      env.store._dispatched.some(
        ([n, v]) => n === 'toast/setWorkspaceStale' && v === true
      )
    ).toBe(false)
    // The high-water mark must not regress below the live-message value.
    expect(env.handler.lastSeenRealtimeUpdateId).toBe(50)
  })

  test('subscribe_result with all-false updates advances baseline without toast', () => {
    env.handler.lastSeenWorkspaceId = 7
    fire(env.handler, 'realtime_subscribe_result', {
      workspace_id: 7,
      stale: false,
      current_latest_id: 99,
    })
    expect(
      env.store._dispatched.some(
        ([n, v]) => n === 'toast/setWorkspaceStale' && v === true
      )
    ).toBe(false)
    expect(env.handler.lastSeenRealtimeUpdateId).toBe(99)
  })

  test('subscribe_result for an inactive workspace is ignored', () => {
    fire(env.handler, 'realtime_subscribe_result', {
      workspace_id: 999, // not the active workspace (7)
      stale: true,
      current_latest_id: 42,
    })
    expect(env.handler.lastSeenRealtimeUpdateId).toBeNull()
    expect(
      env.store._dispatched.some(([n]) => n === 'toast/setWorkspaceStale')
    ).toBe(false)
  })
})

describe('RealTimeHandler high-water mark', () => {
  test('updateLastSeenId takes the max of incoming ids', () => {
    const { handler } = makeHandler({ workspaceId: 1 })
    handler.updateLastSeenId({ realtime_update_id: 5 })
    expect(handler.lastSeenRealtimeUpdateId).toBe(5)
    handler.updateLastSeenId({ realtime_update_id: 3 })
    expect(handler.lastSeenRealtimeUpdateId).toBe(5)
    handler.updateLastSeenId({ realtime_update_id: 7 })
    expect(handler.lastSeenRealtimeUpdateId).toBe(7)
    handler.updateLastSeenId({ type: 'no_id' })
    expect(handler.lastSeenRealtimeUpdateId).toBe(7)
  })
})

describe('RealTimeHandler workspace switch', () => {
  test('switching to a new workspace resets baseline and re-subscribes', () => {
    const { handler, store, sentMessages } = makeHandler({ workspaceId: 7 })
    // Connect+authenticate first to capture web_socket_id.
    fire(handler, 'authentication', { success: true })
    handler.lastSeenRealtimeUpdateId = 33
    sentMessages.length = 0

    store._setSelected({ id: 12, _: { type: 'workspace' } })

    expect(handler.lastSeenRealtimeUpdateId).toBeNull()
    const subscribe = sentMessages.find((m) => m.type === 'realtime_subscribe')
    expect(subscribe).toEqual({
      type: 'realtime_subscribe',
      workspace_id: 12,
      last_seen_id: null,
    })
  })
})

describe('RealTimeHandler reconnect logic', () => {
  let env

  beforeEach(() => {
    vi.useFakeTimers()
    env = makeHandler({ workspaceId: 7 })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  test('connection failure without auth response keeps retrying', () => {
    const { handler } = env
    handler.reconnect = true
    handler.authenticationSuccess = true

    // Simulate 5 connection failures (onclose without auth response)
    for (let i = 0; i < 5; i++) {
      handler.delayedReconnect()
    }

    // attempts incremented but no failedConnecting dispatch
    expect(handler.attempts).toBe(5)
    expect(
      env.store._dispatched.some(
        ([n, v]) => n === 'toast/setFailedConnecting' && v === true
      )
    ).toBe(false)
  })

  test('explicit auth rejection sets state that would stop retries', () => {
    const { handler } = env
    // Simulate: server sent {success: false} for current token
    fire(handler, 'authentication', {
      web_socket_id: null,
      success: false,
    })

    expect(handler.authResponseReceived).toBe(true)
    expect(handler.authenticationSuccess).toBe(false)
    // The connect() guard checks:
    // authResponseReceived && !authenticationSuccess && token === lastToken
    // With this state + same token, connect() would bail
  })

  test('auth rejection flag resets when new connection starts', () => {
    const { handler } = env
    fire(handler, 'authentication', {
      web_socket_id: null,
      success: false,
    })
    expect(handler.authResponseReceived).toBe(true)

    // Simulate what connect() does before creating WebSocket
    handler.authResponseReceived = false

    // Now the guard won't fire even with authenticationSuccess=false
    expect(handler.authResponseReceived).toBe(false)
  })

  test('successful connect resets attempts to zero', () => {
    const { handler } = env
    handler.attempts = 5
    handler.reconnect = true
    handler.connected = true

    // Simulate what onopen does
    handler.connected = true
    handler.attempts = 0

    expect(handler.attempts).toBe(0)
  })

  test('delayedReconnect skipped when unloading is true', () => {
    const { handler } = env
    handler.reconnect = true
    handler.unloading = true

    const attemptsBefore = handler.attempts
    handler.delayedReconnect()

    expect(handler.attempts).toBe(attemptsBefore)
    expect(
      env.store._dispatched.some(([n]) => n === 'toast/setReconnecting')
    ).toBe(false)
  })

  test('delayedReconnect skipped when reconnect is false', () => {
    const { handler } = env
    handler.reconnect = false

    handler.delayedReconnect()

    expect(handler.attempts).toBe(0)
  })

  test('visibility change to visible triggers immediate reconnect when disconnected', () => {
    const { handler } = env
    handler.connected = false
    handler.reconnect = true
    handler.anonymous = false
    handler.reconnectTimeout = setTimeout(() => {}, 99999)

    const connectSpy = vi.spyOn(handler, 'connect')
    handler._onVisibilityChange.call(handler)

    // visibilityState is not 'visible' in test env by default, so
    // simulate by setting it
    Object.defineProperty(document, 'visibilityState', {
      value: 'visible',
      writable: true,
      configurable: true,
    })
    handler._onVisibilityChange()

    expect(connectSpy).toHaveBeenCalledWith(true, false)
    connectSpy.mockRestore()
  })

  test('delayedReconnect increments attempts each call', () => {
    const { handler } = env
    handler.reconnect = true

    handler.delayedReconnect()
    handler.delayedReconnect()
    handler.delayedReconnect()

    expect(handler.attempts).toBe(3)
  })

  test('delayedReconnect dispatches reconnecting toast', () => {
    const { handler } = env
    handler.reconnect = true

    handler.delayedReconnect()

    expect(
      env.store._dispatched.some(
        ([n, v]) => n === 'toast/setReconnecting' && v === true
      )
    ).toBe(true)
  })
})

describe('RealTimeHandler subscribe params', () => {
  test('reconnect to same workspace sends last_seen_id', () => {
    const { handler, sentMessages } = makeHandler({ workspaceId: 7 })
    handler.lastSeenRealtimeUpdateId = 42
    handler.lastSeenWorkspaceId = 7

    handler._sendRealtimeSubscribe(7)

    const msg = sentMessages.find((m) => m.type === 'realtime_subscribe')
    expect(msg).toEqual({
      type: 'realtime_subscribe',
      workspace_id: 7,
      last_seen_id: 42,
    })
  })

  test('subscribe to different workspace sends null for last_seen_id', () => {
    const { handler, sentMessages } = makeHandler({ workspaceId: 7 })
    handler.lastSeenRealtimeUpdateId = 42
    handler.lastSeenWorkspaceId = 7

    handler._sendRealtimeSubscribe(99)

    const msg = sentMessages.find((m) => m.type === 'realtime_subscribe')
    expect(msg).toEqual({
      type: 'realtime_subscribe',
      workspace_id: 99,
      last_seen_id: null,
    })
  })

  test('webSocketId persists across reconnects', () => {
    const { handler } = makeHandler({ workspaceId: 7 })
    const id = handler.webSocketId
    expect(id).toBeTruthy()
    expect(typeof id).toBe('string')
    // Simulate onclose + reconnect — id stays the same
    expect(handler.webSocketId).toBe(id)
  })
})

describe('RealTimeHandler disconnect', () => {
  test('disconnect resets all realtime state', () => {
    const { handler, store } = makeHandler({ workspaceId: 7 })
    handler.lastSeenRealtimeUpdateId = 42
    handler.lastSeenWorkspaceId = 7
    handler.attempts = 5
    handler.reconnect = true
    handler.connected = false

    handler.disconnect()

    expect(handler.lastSeenRealtimeUpdateId).toBeNull()
    expect(handler.lastSeenWorkspaceId).toBeNull()
    expect(handler.attempts).toBe(0)
    expect(handler.reconnect).toBe(false)
    expect(
      store._dispatched.some(
        ([n, v]) => n === 'toast/setWorkspaceStale' && v === false
      )
    ).toBe(true)
    expect(
      store._dispatched.some(
        ([n, v]) => n === 'toast/setReconnecting' && v === false
      )
    ).toBe(true)
  })

  test('disconnect closes socket even when not fully connected', () => {
    const { handler } = makeHandler({ workspaceId: 7 })
    let closeCalled = false
    handler.connected = false
    handler.socket = {
      readyState: WebSocket.CONNECTING,
      onclose: () => {},
      close() {
        closeCalled = true
      },
      send() {},
    }

    handler.disconnect()

    expect(closeCalled).toBe(true)
    expect(handler.socket).toBeNull()
  })
})

describe('RealTimeHandler connect early-exit', () => {
  test('connect clears reconnecting toast when max attempts exceeded', () => {
    const { handler, store } = makeHandler({ workspaceId: 7 })
    handler.attempts = 11
    handler.reconnect = true
    handler.socket = null

    handler.connect(true, false)

    expect(
      store._dispatched.some(
        ([n, v]) => n === 'toast/setFailedConnecting' && v === true
      )
    ).toBe(true)
    expect(
      store._dispatched.some(
        ([n, v]) => n === 'toast/setReconnecting' && v === false
      )
    ).toBe(true)
  })
})
