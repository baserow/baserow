import {
  ClientErrorMap,
  ErrorHandler,
  prepareRequestHeaders,
} from '@baserow/modules/core/plugins/clientHandler'

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

describe('ErrorHandler.getErrorMessage', () => {
  const app = { $i18n: { t: (key) => key } }

  test('explains a rich text image that does not exist', () => {
    // Sent under a dedicated code, because the detail of a request body
    // validation error is never shown.
    const handler = new ErrorHandler(
      makeStore(null),
      app,
      new ClientErrorMap(app),
      { status: 400 },
      'ERROR_USER_FILE_DOES_NOT_EXIST',
      "The user files ['abc_def.png'] do not exist."
    )

    expect(handler.getErrorMessage()).toEqual({
      title: 'clientHandler.userFileDoesNotExistTitle',
      message: 'clientHandler.userFileDoesNotExistDescription',
    })
  })
})
