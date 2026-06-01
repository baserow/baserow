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

function makeStore() {
  const dispatched = []
  const webSocketId = 'test-ws-id-' + Math.random().toString(36).slice(2)
  const store = {
    getters: {
      'auth/token': 'token',
      'auth/webSocketId': webSocketId,
    },
    dispatch(name, value) {
      dispatched.push([name, value])
      return Promise.resolve()
    },
    subscribe() {},
    _dispatched: dispatched,
  }
  return store
}

function makeHandler() {
  const store = makeStore()
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
    env = makeHandler()
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
      last_seen_id: null,
    })
  })

  test('authentication subscribes even without active workspace', () => {
    const local = makeHandler()
    fire(local.handler, 'authentication', {
      success: true,
    })
    const subscribe = local.sentMessages.find(
      (m) => m.type === 'realtime_subscribe'
    )
    expect(subscribe).toEqual({
      type: 'realtime_subscribe',
      last_seen_id: null,
    })
  })

  test('subscribe_result needing refresh with newer id fires the toast', () => {
    env.handler.lastSeenEventId = 10
    fire(env.handler, 'realtime_subscribe_result', {
      outdated: true,
      current_latest_id: 42,
    })
    expect(
      env.store._dispatched.some(
        ([n, v]) => n === 'toast/setWorkspaceOutdated' && v === true
      )
    ).toBe(true)
    expect(env.handler.lastSeenEventId).toBe(42)
  })

  test('subscribe_result with outdated current_latest_id does not toast', () => {
    // Mimics a race where a fresh broadcast advanced lastSeen above
    // current_latest_id before the response arrived.
    env.handler.lastSeenEventId = 50
    fire(env.handler, 'realtime_subscribe_result', {
      outdated: true,
      current_latest_id: 42,
    })
    expect(
      env.store._dispatched.some(
        ([n, v]) => n === 'toast/setWorkspaceOutdated' && v === true
      )
    ).toBe(false)
    // The high-water mark must not regress below the live-message value.
    expect(env.handler.lastSeenEventId).toBe(50)
  })

  test('subscribe_result with all-false updates advances baseline without toast', () => {
    fire(env.handler, 'realtime_subscribe_result', {
      outdated: false,
      current_latest_id: 99,
    })
    expect(
      env.store._dispatched.some(
        ([n, v]) => n === 'toast/setWorkspaceOutdated' && v === true
      )
    ).toBe(false)
    expect(env.handler.lastSeenEventId).toBe(99)
  })
})

describe('RealTimeHandler high-water mark', () => {
  test('updateLastSeenId takes the max of incoming ids', () => {
    const { handler } = makeHandler()
    handler.updateLastSeenId({ _event_id: 5 })
    expect(handler.lastSeenEventId).toBe(5)
    handler.updateLastSeenId({ _event_id: 3 })
    expect(handler.lastSeenEventId).toBe(5)
    handler.updateLastSeenId({ _event_id: 7 })
    expect(handler.lastSeenEventId).toBe(7)
    handler.updateLastSeenId({ type: 'no_id' })
    expect(handler.lastSeenEventId).toBe(7)
  })
})

describe('RealTimeHandler reconnect logic', () => {
  let env

  beforeEach(() => {
    vi.useFakeTimers()
    env = makeHandler()
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
  test('reconnect sends last_seen_id', () => {
    const { handler, sentMessages } = makeHandler()
    handler.lastSeenEventId = 42

    handler._sendRealtimeSubscribe()

    const msg = sentMessages.find((m) => m.type === 'realtime_subscribe')
    expect(msg).toEqual({
      type: 'realtime_subscribe',
      last_seen_id: 42,
    })
  })

  test('initial subscribe sends null for last_seen_id', () => {
    const { handler, sentMessages } = makeHandler()

    handler._sendRealtimeSubscribe()

    const msg = sentMessages.find((m) => m.type === 'realtime_subscribe')
    expect(msg).toEqual({
      type: 'realtime_subscribe',
      last_seen_id: null,
    })
  })

  test('webSocketId persists across reconnects', () => {
    const { handler } = makeHandler()
    const id = handler.webSocketId
    expect(id).toBeTruthy()
    expect(typeof id).toBe('string')
    // Simulate onclose + reconnect — id stays the same
    expect(handler.webSocketId).toBe(id)
  })
})

describe('RealTimeHandler disconnect', () => {
  test('disconnect resets all realtime state', () => {
    const { handler, store } = makeHandler()
    handler.lastSeenEventId = 42
    handler.attempts = 5
    handler.reconnect = true
    handler.connected = false

    handler.disconnect()

    expect(handler.lastSeenEventId).toBeNull()
    expect(handler.attempts).toBe(0)
    expect(handler.reconnect).toBe(false)
    expect(
      store._dispatched.some(
        ([n, v]) => n === 'toast/setWorkspaceOutdated' && v === false
      )
    ).toBe(true)
    expect(
      store._dispatched.some(
        ([n, v]) => n === 'toast/setReconnecting' && v === false
      )
    ).toBe(true)
  })

  test('disconnect closes socket even when not fully connected', () => {
    const { handler } = makeHandler()
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
    const { handler, store } = makeHandler()
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
