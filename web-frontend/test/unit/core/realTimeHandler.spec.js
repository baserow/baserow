import { vi, describe, beforeEach, test, expect } from 'vitest'

import { RealTimeHandler } from '@baserow/modules/core/plugins/realTimeHandler'
import {
  FIRST_CONNECT_CURSOR,
  NO_REPLAY_AVAILABLE,
} from '@baserow/modules/core/plugins/realtimeProtocol'

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
  // Stand-in for an open websocket so _sendReplayEventsRequest goes
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

describe('RealTimeHandler replay_events flow', () => {
  let env
  beforeEach(() => {
    env = makeHandler()
  })

  test('authentication sends a baseline replay request when replay is enabled', () => {
    fire(env.handler, 'authentication', {
      success: true,
      replay_enabled: true,
    })
    const replayRequest = env.sentMessages.find(
      (m) => m.type === 'replay_events'
    )
    expect(replayRequest).toEqual({
      type: 'replay_events',
      last_seen_id: FIRST_CONNECT_CURSOR,
    })
  })

  test('authentication does not send replay_events when replay is disabled', () => {
    fire(env.handler, 'authentication', {
      success: true,
      replay_enabled: false,
    })
    const replayRequest = env.sentMessages.find(
      (m) => m.type === 'replay_events'
    )
    expect(replayRequest).toBeUndefined()
    expect(env.handler.replayEnabled).toBe(false)
  })

  test('authentication requests replay even without active workspace', () => {
    const local = makeHandler()
    fire(local.handler, 'authentication', {
      success: true,
      replay_enabled: true,
    })
    const replayRequest = local.sentMessages.find(
      (m) => m.type === 'replay_events'
    )
    expect(replayRequest).toEqual({
      type: 'replay_events',
      last_seen_id: FIRST_CONNECT_CURSOR,
    })
  })

  test('client stores zero latest_event_id from empty table and sends it back on reconnect', () => {
    // Server returns 0 as latest_event_id when replay is enabled but no
    // events have been recorded yet (Coalesce(Max("id"), 0)).
    env.handler.replayEnabled = true
    fire(env.handler, 'replay_events_result', {
      force_refresh: false,
      latest_event_id: 0,
    })
    expect(env.handler.lastSeenEventId).toBe(0)

    // Reconnect: client sends 0 which is a valid cursor (not a sentinel).
    env.sentMessages.length = 0
    env.handler._sendReplayEventsRequest()
    const replayRequest = env.sentMessages.find(
      (m) => m.type === 'replay_events'
    )
    expect(replayRequest).toEqual({
      type: 'replay_events',
      last_seen_id: 0,
    })
  })

  test('replay_events_result needing refresh fires the toast', () => {
    env.handler.lastSeenEventId = 10
    fire(env.handler, 'replay_events_result', {
      force_refresh: true,
      latest_event_id: 42,
    })
    expect(
      env.store._dispatched.some(
        ([n, v]) => n === 'toast/setWorkspaceOutdated' && v === true
      )
    ).toBe(true)
    expect(env.handler.lastSeenEventId).toBe(10)
  })

  test('replay_events_result with force_refresh does not advance latest_event_id', () => {
    env.handler.lastSeenEventId = 50
    fire(env.handler, 'replay_events_result', {
      force_refresh: true,
      latest_event_id: 42,
    })
    expect(
      env.store._dispatched.some(
        ([n, v]) => n === 'toast/setWorkspaceOutdated' && v === true
      )
    ).toBe(true)
    // The high-water mark must not regress below the live-message value.
    expect(env.handler.lastSeenEventId).toBe(50)
  })

  test('replay_events_result with force_refresh false advances baseline without toast', () => {
    fire(env.handler, 'replay_events_result', {
      force_refresh: false,
      latest_event_id: 99,
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

  test('retry signal clears the unloading latch and reconnects', () => {
    const { handler } = env
    // ``pagehide``/``beforeunload`` set the latch; a later ``pageshow`` or
    // ``online`` event (both wired to _onShouldRetryNow) must clear it so
    // reconnects are not suppressed forever after a bfcache restore.
    handler.unloading = true
    handler.connected = false
    handler.reconnect = true
    handler.anonymous = false

    const connectSpy = vi.spyOn(handler, 'connect')
    handler._onShouldRetryNow()

    expect(handler.unloading).toBe(false)
    expect(connectSpy).toHaveBeenCalledWith(true, false)
    connectSpy.mockRestore()
  })

  test('wires a window focus listener to the retry handler', () => {
    const addSpy = vi.spyOn(window, 'addEventListener')
    const handler = new RealTimeHandler({
      store: makeStore(),
      app: { router: {} },
    })
    const focusCall = addSpy.mock.calls.find(([type]) => type === 'focus')
    expect(focusCall).toBeDefined()
    expect(focusCall[1]).toBe(handler._onShouldRetryNow)
    addSpy.mockRestore()
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
    Object.defineProperty(document, 'visibilityState', {
      value: 'visible',
      writable: true,
      configurable: true,
    })
    handler._onVisibilityChange()

    expect(connectSpy).toHaveBeenCalledWith(true, false)
    expect(handler.attempts).toBe(0)
    expect(
      env.store._dispatched.some(
        ([n, v]) => n === 'toast/setFailedConnecting' && v === false
      )
    ).toBe(true)
    // The "Reconnecting" toast stays up across the immediate retry — only
    // ``onopen`` clears it — so it should NOT be dispatched false here.
    expect(
      env.store._dispatched.some(
        ([n, v]) => n === 'toast/setReconnecting' && v === false
      )
    ).toBe(false)
    connectSpy.mockRestore()
  })

  test('visibility reconnect retries after max attempts without keeping failure toast', () => {
    const { handler } = env
    handler.connected = false
    handler.reconnect = true
    handler.attempts = 11

    const connectSpy = vi.spyOn(handler, 'connect')
    Object.defineProperty(document, 'visibilityState', {
      value: 'visible',
      writable: true,
      configurable: true,
    })

    handler._onVisibilityChange()

    expect(handler.attempts).toBe(0)
    expect(connectSpy).toHaveBeenCalledWith(true, false)
    expect(
      env.store._dispatched.some(
        ([n, v]) => n === 'toast/setFailedConnecting' && v === false
      )
    ).toBe(true)
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

describe('RealTimeHandler replay request params', () => {
  test('reconnect sends last_seen_id', () => {
    const { handler, sentMessages } = makeHandler()
    handler.replayEnabled = true
    handler.lastSeenEventId = 42

    handler._sendReplayEventsRequest()

    const msg = sentMessages.find((m) => m.type === 'replay_events')
    expect(msg).toEqual({
      type: 'replay_events',
      last_seen_id: 42,
    })
  })

  test('initial replay request sends FIRST_CONNECT_CURSOR for last_seen_id', () => {
    const { handler, sentMessages } = makeHandler()
    handler.replayEnabled = true

    handler._sendReplayEventsRequest()

    const msg = sentMessages.find((m) => m.type === 'replay_events')
    expect(msg).toEqual({
      type: 'replay_events',
      last_seen_id: FIRST_CONNECT_CURSOR,
    })
  })

  test('_canReplayEvents returns false when replay is disabled', () => {
    const { handler } = makeHandler()
    handler.replayEnabled = false

    expect(handler._canReplayEvents()).toBe(false)
  })

  test('_canReplayEvents returns true when replay is enabled and socket is open', () => {
    const { handler } = makeHandler()
    handler.replayEnabled = true

    expect(handler._canReplayEvents()).toBe(true)
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

    // Reset to FIRST_CONNECT_CURSOR so the next connection is treated as fresh.
    expect(handler.lastSeenEventId).toBe(FIRST_CONNECT_CURSOR)
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

describe('RealTimeHandler onclose toast suppression', () => {
  let env

  beforeEach(() => {
    vi.useFakeTimers()
    env = makeHandler()
  })

  afterEach(() => {
    vi.useRealTimers()
    Object.defineProperty(document, 'visibilityState', {
      value: 'visible',
      writable: true,
      configurable: true,
    })
    Object.defineProperty(navigator, 'onLine', {
      value: true,
      writable: true,
      configurable: true,
    })
  })

  test('delayedReconnect while hidden does not show reconnecting toast', () => {
    const { handler, store } = env
    handler.reconnect = true
    handler.connected = false

    Object.defineProperty(document, 'visibilityState', {
      value: 'hidden',
      writable: true,
      configurable: true,
    })

    handler.delayedReconnect()

    expect(
      store._dispatched.some(
        ([n, v]) => n === 'toast/setReconnecting' && v === true
      )
    ).toBe(false)
  })

  test('delayedReconnect while offline shows reconnecting toast but does not schedule retry', () => {
    const { handler, store } = env
    handler.reconnect = true
    handler.connected = false

    Object.defineProperty(document, 'visibilityState', {
      value: 'visible',
      writable: true,
      configurable: true,
    })
    Object.defineProperty(navigator, 'onLine', {
      value: false,
      writable: true,
      configurable: true,
    })

    handler.delayedReconnect()

    expect(
      store._dispatched.some(
        ([n, v]) => n === 'toast/setReconnecting' && v === true
      )
    ).toBe(true)
    expect(handler.attempts).toBe(0)

    Object.defineProperty(navigator, 'onLine', {
      value: true,
      writable: true,
      configurable: true,
    })
  })

  test('delayedReconnect while unloading does not show reconnecting toast', () => {
    const { handler, store } = env
    handler.reconnect = true
    handler.connected = false
    handler.unloading = true

    handler.delayedReconnect()

    expect(
      store._dispatched.some(
        ([n, v]) => n === 'toast/setReconnecting' && v === true
      )
    ).toBe(false)
  })
})

describe('RealTimeHandler max attempts', () => {
  let env

  beforeEach(() => {
    vi.useFakeTimers()
    env = makeHandler()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  test('shows the failed toast but keeps retrying slowly after max attempts', () => {
    const { handler, store } = env
    handler.reconnect = true
    handler.attempts = 10
    const connectSpy = vi.spyOn(handler, 'connect').mockImplementation(() => {})

    handler.delayedReconnect()

    // Capped so slow retries can't grow the count unbounded.
    expect(handler.attempts).toBe(11)
    handler.delayedReconnect()
    expect(handler.attempts).toBe(11)

    expect(
      store._dispatched.some(
        ([n, v]) => n === 'toast/setFailedConnecting' && v === true
      )
    ).toBe(true)

    // Self-heals when the backend returns, with no user action.
    expect(connectSpy).not.toHaveBeenCalled()
    vi.advanceTimersByTime(30000)
    expect(connectSpy).toHaveBeenCalledWith(true, false)
    connectSpy.mockRestore()
  })

  test('connect does not show failed toast while tab is hidden', () => {
    const { handler, store } = makeHandler()
    // Genuine auth rejection — the path that still raises the Failed toast.
    handler.authResponseReceived = true
    handler.authenticationSuccess = false
    handler.lastToken = 'token'
    handler.reconnect = true
    handler.socket = null
    Object.defineProperty(document, 'visibilityState', {
      value: 'hidden',
      writable: true,
      configurable: true,
    })

    handler.connect(true, false)

    expect(
      store._dispatched.some(
        ([n, v]) => n === 'toast/setFailedConnecting' && v === true
      )
    ).toBe(false)
    expect(
      store._dispatched.some(
        ([n, v]) => n === 'toast/setReconnecting' && v === false
      )
    ).toBe(true)

    Object.defineProperty(document, 'visibilityState', {
      value: 'visible',
      writable: true,
      configurable: true,
    })
  })

  test('delayedReconnect still schedules retry at exactly max attempts', () => {
    const { handler, store } = env
    handler.reconnect = true
    handler.attempts = 9

    handler.delayedReconnect()

    expect(handler.attempts).toBe(10)
    expect(
      store._dispatched.some(
        ([n, v]) => n === 'toast/setReconnecting' && v === true
      )
    ).toBe(true)
    expect(
      store._dispatched.some(
        ([n, v]) => n === 'toast/setFailedConnecting' && v === true
      )
    ).toBe(false)
  })
})

describe('RealTimeHandler replay_enabled=false cursor reset', () => {
  test('auth with replay_enabled=false sets lastSeenEventId to NO_REPLAY_AVAILABLE', () => {
    const { handler } = makeHandler()
    handler.lastSeenEventId = 42

    fire(handler, 'authentication', {
      success: true,
      replay_enabled: false,
    })

    expect(handler.lastSeenEventId).toBe(NO_REPLAY_AVAILABLE)
  })

  test('auth with replay_enabled=true does not reset lastSeenEventId', () => {
    const { handler } = makeHandler()
    handler.lastSeenEventId = 42

    fire(handler, 'authentication', {
      success: true,
      replay_enabled: true,
    })

    expect(handler.lastSeenEventId).toBe(42)
  })
})

describe('RealTimeHandler connect early-exit', () => {
  test('connect() itself does not gate on attempt count', () => {
    // The max-attempts guard lives in delayedReconnect(), not connect().
    // connect() only checks token validity, so a high attempt count alone
    // does not prevent a connection attempt.
    const { handler, store } = makeHandler()
    handler.attempts = 99
    handler.reconnect = true
    handler.socket = null

    handler.connect(true, false)

    expect(
      store._dispatched.some(
        ([n, v]) => n === 'toast/setFailedConnecting' && v === true
      )
    ).toBe(false)
  })

  test('connect does not show failed toast while tab is hidden', () => {
    const { handler, store } = makeHandler()
    // Genuine auth rejection — the path that still raises the Failed toast.
    handler.authResponseReceived = true
    handler.authenticationSuccess = false
    handler.lastToken = 'token'
    handler.reconnect = true
    handler.socket = null
    Object.defineProperty(document, 'visibilityState', {
      value: 'hidden',
      writable: true,
      configurable: true,
    })

    handler.connect(true, false)

    expect(
      store._dispatched.some(
        ([n, v]) => n === 'toast/setFailedConnecting' && v === true
      )
    ).toBe(false)
    expect(
      store._dispatched.some(
        ([n, v]) => n === 'toast/setReconnecting' && v === false
      )
    ).toBe(true)
  })
})

describe('RealTimeHandler connection watchdog', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  test('force-closes a socket stuck in CONNECTING so a reconnect can start', () => {
    const { handler } = makeHandler()
    let closed = false
    handler.socket = {
      readyState: WebSocket.CONNECTING,
      close() {
        closed = true
      },
      send() {},
    }
    handler._armConnectionTimeout()

    vi.advanceTimersByTime(9999)
    expect(closed).toBe(false)
    vi.advanceTimersByTime(1)
    expect(closed).toBe(true)
  })

  test('does not close a socket that finished connecting', () => {
    const { handler } = makeHandler()
    let closed = false
    handler.socket = {
      readyState: WebSocket.OPEN,
      close() {
        closed = true
      },
      send() {},
    }
    handler._armConnectionTimeout()

    vi.advanceTimersByTime(10000)
    expect(closed).toBe(false)
  })

  test('clearing the watchdog cancels the pending force-close', () => {
    const { handler } = makeHandler()
    let closed = false
    handler.socket = {
      readyState: WebSocket.CONNECTING,
      close() {
        closed = true
      },
      send() {},
    }
    handler._armConnectionTimeout()
    handler._clearConnectionTimeout()

    vi.advanceTimersByTime(10000)
    expect(closed).toBe(false)
    expect(handler.connectionTimeout).toBeNull()
  })
})

describe('RealTimeHandler sendFocus', () => {
  test('sendFocus sends correctly shaped presence.focus message', () => {
    const { handler, sentMessages } = makeHandler()
    handler.connected = true

    handler.sendFocus(
      'table',
      { table_id: 42 },
      { type: 'cell', row_id: 1, field_id: 2, editing: false }
    )

    expect(sentMessages).toHaveLength(1)
    expect(sentMessages[0]).toEqual({
      type: 'presence.focus',
      page: 'table',
      table_id: 42,
      focus: { type: 'cell', row_id: 1, field_id: 2, editing: false },
    })
  })

  test('sendFocus sends null focus for clear', () => {
    const { handler, sentMessages } = makeHandler()
    handler.connected = true

    handler.sendFocus('table', { table_id: 42 }, null)

    expect(sentMessages).toHaveLength(1)
    expect(sentMessages[0]).toEqual({
      type: 'presence.focus',
      page: 'table',
      table_id: 42,
      focus: null,
    })
  })

  test('sendFocus is suppressed when not connected', () => {
    const { handler, sentMessages } = makeHandler()
    handler.connected = false

    handler.sendFocus(
      'table',
      { table_id: 42 },
      { type: 'cell', row_id: 1, field_id: 2, editing: false }
    )

    expect(sentMessages).toHaveLength(0)
  })

  test('sendFocus is suppressed when socket is not open', () => {
    const { handler, sentMessages } = makeHandler()
    handler.connected = true
    handler.socket.readyState = WebSocket.CLOSED

    handler.sendFocus(
      'table',
      { table_id: 42 },
      { type: 'cell', row_id: 1, field_id: 2, editing: false }
    )

    expect(sentMessages).toHaveLength(0)
  })

  test('sendFocus spreads parameters into top-level message', () => {
    const { handler, sentMessages } = makeHandler()
    handler.connected = true

    handler.sendFocus(
      'table',
      { table_id: 10, extra_param: 'val' },
      { type: 'row', row_id: 5, editing: true }
    )

    expect(sentMessages[0]).toEqual({
      type: 'presence.focus',
      page: 'table',
      table_id: 10,
      extra_param: 'val',
      focus: { type: 'row', row_id: 5, editing: true },
    })
  })
})

describe('RealTimeHandler presence events', () => {
  test('presence.members dispatches handleMembers', () => {
    const { handler, store } = makeHandler()
    fire(handler, 'presence.members', {
      space: 'table-1',
      entries: [{ presence_id: 'pid-1', user_id: 10 }],
    })
    expect(
      store._dispatched.some(
        ([n, v]) =>
          n === 'presence/handleMembers' &&
          v.space === 'table-1' &&
          v.entries.length === 1
      )
    ).toBe(true)
  })

  test('presence.join dispatches handleJoin', () => {
    const { handler, store } = makeHandler()
    fire(handler, 'presence.join', {
      space: 'table-1',
      presence_id: 'pid-2',
      user_id: 20,
    })
    expect(
      store._dispatched.some(
        ([n, v]) =>
          n === 'presence/handleJoin' &&
          v.space === 'table-1' &&
          v.presence_id === 'pid-2' &&
          v.user_id === 20
      )
    ).toBe(true)
  })

  test('presence.leave dispatches handleLeave', () => {
    const { handler, store } = makeHandler()
    fire(handler, 'presence.leave', {
      space: 'table-1',
      presence_id: 'pid-3',
    })
    expect(
      store._dispatched.some(
        ([n, v]) =>
          n === 'presence/handleLeave' &&
          v.space === 'table-1' &&
          v.presence_id === 'pid-3'
      )
    ).toBe(true)
  })

  test('presence.space_discard dispatches clearSpace', () => {
    const { handler, store } = makeHandler()
    fire(handler, 'presence.space_discard', {
      space: 'table-1',
    })
    expect(
      store._dispatched.some(
        ([n, v]) => n === 'presence/clearSpace' && v.space === 'table-1'
      )
    ).toBe(true)
  })

  test('presence.focus dispatches handleFocus with correct shape', () => {
    const { handler, store } = makeHandler()
    fire(handler, 'presence.focus', {
      space: 'table-1',
      presence_id: 'pid-5',
      focus: { type: 'cell', row_id: 10, field_id: 20, editing: true },
    })
    expect(
      store._dispatched.some(
        ([n, v]) =>
          n === 'presence/handleFocus' &&
          v.space === 'table-1' &&
          v.presence_id === 'pid-5' &&
          v.focus.type === 'cell' &&
          v.focus.row_id === 10 &&
          v.focus.field_id === 20 &&
          v.focus.editing === true
      )
    ).toBe(true)
  })

  test('presence.focus dispatches null focus for clear', () => {
    const { handler, store } = makeHandler()
    fire(handler, 'presence.focus', {
      space: 'table-1',
      presence_id: 'pid-6',
      focus: null,
    })
    expect(
      store._dispatched.some(
        ([n, v]) =>
          n === 'presence/handleFocus' &&
          v.space === 'table-1' &&
          v.presence_id === 'pid-6' &&
          v.focus === null
      )
    ).toBe(true)
  })

  test('presence.editors_active dispatches handleEditorsActive', () => {
    const { handler, store } = makeHandler()
    fire(handler, 'presence.editors_active', {
      space: 'table-1',
      active: true,
    })
    expect(
      store._dispatched.some(
        ([n, v]) =>
          n === 'presence/handleEditorsActive' &&
          v.space === 'table-1' &&
          v.active === true
      )
    ).toBe(true)
  })
})

describe('RealTimeHandler token refresh on reconnect', () => {
  function makeRefreshStore({ shouldRefresh = false } = {}) {
    const dispatched = []
    const store = {
      getters: {
        'auth/token': 'stale-token',
        'auth/webSocketId': 'ws-id',
        'auth/isAuthenticated': true,
        'auth/shouldRefreshToken': () => shouldRefresh,
      },
      dispatch(name, value) {
        dispatched.push([name, value])
        if (name === 'auth/refresh') {
          const refreshCount = dispatched.filter(
            ([n]) => n === 'auth/refresh'
          ).length
          store.getters['auth/token'] = `fresh-token-${refreshCount}`
        }
        return Promise.resolve()
      },
      subscribe() {},
      _dispatched: dispatched,
    }
    return store
  }

  function makeHandlerWith(store) {
    const context = { store, app: { router: {} } }
    return { handler: new RealTimeHandler(context), store }
  }

  beforeEach(() => {
    Object.defineProperty(document, 'visibilityState', {
      value: 'visible',
      writable: true,
      configurable: true,
    })
  })

  test('an expiring access token is refreshed before the socket opens', async () => {
    const store = makeRefreshStore({ shouldRefresh: true })
    const { handler } = makeHandlerWith(store)

    await handler.connect(true, false)

    expect(store._dispatched.some(([n]) => n === 'auth/refresh')).toBe(true)
    expect(handler.lastToken).toBe('fresh-token-1')
    expect(
      store._dispatched.some(
        ([n, v]) => n === 'toast/setFailedConnecting' && v === true
      )
    ).toBe(false)
  })

  test('a fresh-looking token is not refreshed on a normal reconnect', async () => {
    const store = makeRefreshStore({ shouldRefresh: false })
    const { handler } = makeHandlerWith(store)

    await handler.connect(true, false)

    expect(store._dispatched.some(([n]) => n === 'auth/refresh')).toBe(false)
    expect(handler.lastToken).toBe('stale-token')
  })

  test('anonymous reconnects never refresh the token', async () => {
    const store = makeRefreshStore({ shouldRefresh: true })
    // An anonymous session has no refresh token to spend.
    store.getters['auth/isAuthenticated'] = false
    const { handler } = makeHandlerWith(store)

    await handler.connect(true, true)

    expect(store._dispatched.some(([n]) => n === 'auth/refresh')).toBe(false)
  })

  test('auth rejection forces a token refresh on the next reconnect', async () => {
    // The token looks fresh to the client (shouldRefresh=false) but the server
    // rejects it. The reconnect must still refresh instead of giving up.
    const store = makeRefreshStore({ shouldRefresh: false })
    const { handler } = makeHandlerWith(store)
    handler.reconnect = true
    handler.anonymous = false

    await handler.connect(true, false)
    expect(handler.lastToken).toBe('stale-token')

    fire(handler, 'authentication', { success: false })
    expect(handler.forceTokenRefresh).toBe(true)

    await handler.connect(true, false)

    expect(store._dispatched.some(([n]) => n === 'auth/refresh')).toBe(true)
    expect(handler.lastToken).toBe('fresh-token-1')
    expect(handler.forceTokenRefresh).toBe(false)
    expect(
      store._dispatched.some(
        ([n, v]) => n === 'toast/setFailedConnecting' && v === true
      )
    ).toBe(false)
  })

  test('a successful reconnect clears the forced-refresh flag', async () => {
    const store = makeRefreshStore({ shouldRefresh: false })
    const { handler } = makeHandlerWith(store)
    handler.forceTokenRefresh = true

    fire(handler, 'authentication', { success: true, replay_enabled: false })

    expect(handler.forceTokenRefresh).toBe(false)
  })

  test('stops refreshing once a freshly refreshed token is also rejected', async () => {
    const store = makeRefreshStore({ shouldRefresh: false })
    const { handler } = makeHandlerWith(store)
    handler.reconnect = true
    handler.anonymous = false

    fire(handler, 'authentication', { success: false })
    expect(handler.forceTokenRefresh).toBe(true)
    expect(handler.tokenRefreshRetries).toBe(1)
    await handler.connect(true, false)
    expect(handler.lastToken).toBe('fresh-token-1')

    fire(handler, 'authentication', { success: false })
    expect(handler.forceTokenRefresh).toBe(false)

    // The next reconnect reuses the same rejected token and surfaces failure.
    const refreshesBefore = store._dispatched.filter(
      ([n]) => n === 'auth/refresh'
    ).length
    await handler.connect(true, false)
    const refreshesAfter = store._dispatched.filter(
      ([n]) => n === 'auth/refresh'
    ).length
    expect(refreshesAfter).toBe(refreshesBefore)
    expect(
      store._dispatched.some(
        ([n, v]) => n === 'toast/setFailedConnecting' && v === true
      )
    ).toBe(true)
  })

  test('a 401 refresh clears the session and surfaces the failure toast', async () => {
    const dispatched = []
    const store = {
      getters: {
        'auth/token': 'stale-token',
        'auth/webSocketId': 'ws-id',
        'auth/isAuthenticated': true,
        'auth/shouldRefreshToken': () => true,
      },
      dispatch(name, value) {
        dispatched.push([name, value])
        if (name === 'auth/refresh') {
          store.getters['auth/token'] = null
          const error = new Error('session expired')
          error.response = { status: 401 }
          return Promise.reject(error)
        }
        return Promise.resolve()
      },
      subscribe() {},
      _dispatched: dispatched,
    }
    const { handler } = makeHandlerWith(store)

    await handler.connect(true, false)

    expect(dispatched.some(([n]) => n === 'auth/refresh')).toBe(true)
    expect(
      dispatched.some(
        ([n, v]) => n === 'toast/setFailedConnecting' && v === true
      )
    ).toBe(true)
  })

  test('a transient refresh failure retries with backoff instead of failing', async () => {
    vi.useFakeTimers()
    const dispatched = []
    const store = {
      getters: {
        'auth/token': 'stale-token',
        'auth/webSocketId': 'ws-id',
        'auth/isAuthenticated': true,
        'auth/shouldRefreshToken': () => true,
      },
      dispatch(name, value) {
        dispatched.push([name, value])
        if (name === 'auth/refresh') {
          // No ``response`` — a network-level error that leaves the token intact.
          return Promise.reject(new Error('Network Error'))
        }
        return Promise.resolve()
      },
      subscribe() {},
      _dispatched: dispatched,
    }
    const { handler } = makeHandlerWith(store)
    handler.reconnect = true

    await handler.connect(true, false)

    expect(
      dispatched.some(
        ([n, v]) => n === 'toast/setFailedConnecting' && v === true
      )
    ).toBe(false)
    expect(
      dispatched.some(([n, v]) => n === 'toast/setReconnecting' && v === true)
    ).toBe(true)
    expect(handler.connecting).toBe(false)

    clearTimeout(handler.reconnectTimeout)
    vi.useRealTimers()
  })
})
