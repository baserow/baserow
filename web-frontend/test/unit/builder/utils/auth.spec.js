import { consumeLoginError } from '@baserow/modules/builder/utils/auth'

/**
 * Builds a registry returning an auth provider type that reports an error for the
 * given user source id, mimicking the SSO provider types which read their own error
 * query parameter.
 */
const registryFor = (userSourceIdWithError, message = 'Login failed') => ({
  get: () => ({
    getLoginError(userSource, route) {
      return route.query[`saml_error__${userSource.id}`] &&
        userSource.id === userSourceIdWithError
        ? message
        : null
    },
  }),
})

const userSource = (id) => ({ id, auth_providers: [{ type: 'saml' }] })

describe('consumeLoginError', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/')
  })

  test('returns the error of the user source it belongs to', () => {
    window.history.replaceState({}, '', '/?saml_error__42=errorSomething')

    expect(
      consumeLoginError(registryFor(42), [userSource(1), userSource(42)])
    ).toBe('Login failed')
  })

  test('returns null when no user source reports an error', () => {
    window.history.replaceState({}, '', '/?saml_error__42=errorSomething')

    // The error is in the URL but belongs to a user source that isn't checked.
    expect(consumeLoginError(registryFor(42), [userSource(1)])).toBeNull()
  })

  test('returns null when there is no error parameter at all', () => {
    expect(consumeLoginError(registryFor(42), [userSource(42)])).toBeNull()
  })

  test('reads the query parameters from the location and not from the route', () => {
    // The auth form element removes the parameter with `history.replaceState`, which
    // doesn't update the router route, so the location is the only reliable source.
    window.history.replaceState({}, '', '/?saml_error__42=errorSomething')
    expect(consumeLoginError(registryFor(42), [userSource(42)])).toBe(
      'Login failed'
    )

    window.history.replaceState({}, '', '/')
    expect(consumeLoginError(registryFor(42), [userSource(42)])).toBeNull()
  })

  test('skips user sources without auth providers', () => {
    window.history.replaceState({}, '', '/?saml_error__42=errorSomething')

    expect(
      consumeLoginError(registryFor(42), [{ id: 42 }, userSource(42)])
    ).toBe('Login failed')
  })
})
