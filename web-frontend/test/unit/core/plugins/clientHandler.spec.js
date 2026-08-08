import { prepareRequestHeaders } from '@baserow/modules/core/plugins/clientHandler'

const makeStore = (webSocketId) => ({
  getters: {
    'userSourceUser/getCurrentApplication': null,
    'auth/isAuthenticated': false,
    'userSourceUser/isAuthenticated': () => false,
    'auth/webSocketId': webSocketId,
  },
})

describe('prepareRequestHeaders', () => {
  test('sends the web socket id by default', () => {
    const config = prepareRequestHeaders(makeStore('abc'))({ headers: {} })

    expect(config.headers.WebSocketId).toBe('abc')
  })

  test('omits the web socket id when the request opts out', () => {
    // The realtime layer leaves the sender out of the broadcast, so a request
    // whose changes are made server side has to opt out of that.
    const config = prepareRequestHeaders(makeStore('abc'))({
      headers: {},
      omitWebSocketId: true,
    })

    expect(config.headers.WebSocketId).toBeUndefined()
  })

  test('sends nothing when there is no web socket id', () => {
    const config = prepareRequestHeaders(makeStore(null))({ headers: {} })

    expect(config.headers.WebSocketId).toBeUndefined()
  })
})
