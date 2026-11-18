import { prepareUserSourceRequestHeaders } from '@baserow/modules/core/plugins/userSourceClientHandler'

function createStore({ baserowUserAuthenticated = false } = {}) {
  const application = { id: 1 }
  return {
    getters: {
      'userSourceUser/getCurrentApplication': application,
      'userSourceUser/isAuthenticated': () => true,
      'userSourceUser/isRefreshing': () => false,
      'userSourceUser/accessToken': () => 'app-user-token',
      'auth/isAuthenticated': baserowUserAuthenticated,
    },
  }
}

describe('prepareUserSourceRequestHeaders', () => {
  test('sends the user source token of a logged in visitor', () => {
    const config = prepareUserSourceRequestHeaders(createStore())({})

    expect(config.headers.Authorization).toBe('JWT app-user-token')
    expect(config.usesUserSourceAuthorization).toBe(true)
  })

  test('sends no user source token when the request opts out', () => {
    const config = prepareUserSourceRequestHeaders(createStore())({
      skipUserSourceAuthorization: true,
    })

    expect(config.headers?.Authorization).toBeUndefined()
    expect(config.headers?.UserSourceAuthorization).toBeUndefined()
    expect(config.usesUserSourceAuthorization).toBeUndefined()
  })

  test('sends no user source header next to a Baserow user when opting out', () => {
    const config = prepareUserSourceRequestHeaders(
      createStore({ baserowUserAuthenticated: true })
    )({ skipUserSourceAuthorization: true })

    expect(config.headers?.UserSourceAuthorization).toBeUndefined()
  })
})
