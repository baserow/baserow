import { TestApp } from '@baserow/test/helpers/testApp'

describe('Auth store', () => {
  let testApp = null
  let store = null
  let fakeUserData = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
    fakeUserData = {
      user: {
        id: 256,
      },
      access_token:
        `eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VybmFtZSI6ImpvaG5AZXhhb` +
        `XBsZS5jb20iLCJpYXQiOjE2NjAyOTEwODYsImV4cCI6MTY2MDI5NDY4NiwianRpIjo` +
        `iNDZmNzUwZWUtMTJhMS00N2UzLWJiNzQtMDIwYWM4Njg3YWMzIiwidXNlcl9pZCI6M` +
        `iwidXNlcl9wcm9maWxlX2lkIjpbMl0sIm9yaWdfaWF0IjoxNjYwMjkxMDg2fQ.RQ-M` +
        `NQdDR9zTi8CbbQkRrwNsyDa5CldQI83Uid1l9So`,
    }
    store.dispatch('auth/forceSetUserData', {
      ...fakeUserData,
    })
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('updating user preferences is optimistic and keeps the local value', async () => {
    store.dispatch('auth/forceUpdateUserData', {
      user: { preferences: { sort: 'created', mode: 'expanded' } },
    })
    testApp.mock
      .onPatch('/user/preferences/', { sort: 'name_asc' })
      .reply(200, { sort: 'name_asc', mode: 'expanded' })

    const promise = store.dispatch('auth/updateUserPreferences', {
      sort: 'name_asc',
    })
    expect(store.getters['auth/getUserPreference']('sort')).toBe('name_asc')
    await promise
    expect(store.getters['auth/getUserPreferences']).toStrictEqual({
      sort: 'name_asc',
      mode: 'expanded',
    })
  })

  test('updating user preferences rolls back when the request fails', async () => {
    store.dispatch('auth/forceUpdateUserData', {
      user: { preferences: { sort: 'created' } },
    })
    testApp.mock.onPatch('/user/preferences/').reply(400, {
      error: 'ERROR_REQUEST_BODY_VALIDATION',
    })

    await expect(
      store.dispatch('auth/updateUserPreferences', { sort: 'bogus' })
    ).rejects.toBeTruthy()
    expect(store.getters['auth/getUserPreference']('sort')).toBe('created')
  })

  test('a failed write does not undo a newer change of the same key', async () => {
    store.dispatch('auth/forceUpdateUserData', {
      user: { preferences: { sort: 'created' } },
    })
    testApp.mock.onPatch('/user/preferences/').reply((config) => {
      const values = JSON.parse(config.data)
      return values.sort === 'name_asc' ? [500, {}] : [200, values]
    })

    const failing = store.dispatch('auth/updateUserPreferences', {
      sort: 'name_asc',
    })
    const newer = store.dispatch('auth/updateUserPreferences', {
      sort: 'name_desc',
    })
    await expect(failing).rejects.toBeTruthy()
    await newer
    expect(store.getters['auth/getUserPreference']('sort')).toBe('name_desc')
  })

  test('a token refresh during a write does not undo it', async () => {
    const oldUser = { id: 256, preferences: { sort: 'created' } }
    store.dispatch('auth/forceSetUserData', { ...fakeUserData, user: oldUser })
    testApp.mock.onPatch('/user/preferences/').reply(async (config) => {
      // The client refreshes the access token before a request once it nears
      // expiry; that response carries the user as the backend still knows it.
      await store.dispatch('auth/forceSetUserData', {
        ...fakeUserData,
        user: { id: 256, preferences: { sort: 'created' } },
      })
      return [200, JSON.parse(config.data)]
    })

    await store.dispatch('auth/updateUserPreferences', { sort: 'name_asc' })
    expect(store.getters['auth/getUserPreference']('sort')).toBe('name_asc')
  })

  test('a preference response for a previous user does not touch the next', async () => {
    store.dispatch('auth/forceSetUserData', {
      ...fakeUserData,
      user: { id: 256, preferences: { sort: 'created' } },
    })
    let resolveResponse
    let requestSent
    const sent = new Promise((resolve) => (requestSent = resolve))
    testApp.mock.onPatch('/user/preferences/').reply(() => {
      requestSent()
      return new Promise((resolve) => (resolveResponse = resolve))
    })

    const promise = store.dispatch('auth/updateUserPreferences', {
      sort: 'name_asc',
    })
    await sent
    // Another account signs in while the request of the first is still out.
    await store.dispatch('auth/forceLogoff')
    store.dispatch('auth/forceSetUserData', {
      ...fakeUserData,
      user: { id: 257, preferences: { sort: 'name_desc' } },
    })
    resolveResponse([200, { sort: 'name_asc' }])
    await promise

    expect(store.getters['auth/getUserId']).toBe(257)
    expect(store.getters['auth/getUserPreference']('sort')).toBe('name_desc')
  })

  test('a preference response after a logout is ignored', async () => {
    store.dispatch('auth/forceSetUserData', {
      ...fakeUserData,
      user: { id: 256, preferences: { sort: 'created' } },
    })
    testApp.mock.onPatch('/user/preferences/').reply(200, { sort: 'name_asc' })

    const promise = store.dispatch('auth/updateUserPreferences', {
      sort: 'name_asc',
    })
    await store.dispatch('auth/forceLogoff')
    await promise
    expect(store.getters['auth/isAuthenticated']).toBe(false)
  })

  test('can update a users additional data', () => {
    store.dispatch('auth/forceUpdateUserData', {
      active_licenses: {
        per_workspace: { workspaceId: { test: true } },
      },
    })
    const additionalData = store.getters['auth/getAdditionalUserData']
    expect(JSON.parse(JSON.stringify(additionalData))).toStrictEqual({
      active_licenses: {
        per_workspace: { workspaceId: { test: true } },
      },
    })
  })

  test('updating a users additional data merges with existing values', () => {
    store.dispatch('auth/forceUpdateUserData', {
      active_licenses: {
        per_workspace: { workspaceId: { test: true } },
      },
    })
    store.dispatch('auth/forceUpdateUserData', {
      active_licenses: {
        per_workspace: { workspaceId: { otherKey: true } },
      },
    })
    const additionalData = store.getters['auth/getAdditionalUserData']
    expect(JSON.parse(JSON.stringify(additionalData))).toStrictEqual({
      active_licenses: {
        per_workspace: { workspaceId: { test: true, otherKey: true } },
      },
    })
  })

  test('updating a users additional data overrides arrays', () => {
    store.dispatch('auth/forceUpdateUserData', {
      array_data: [1, 2, 3],
    })
    store.dispatch('auth/forceUpdateUserData', {
      array_data: [3, 4, 5],
    })
    const additionalData = store.getters['auth/getAdditionalUserData']
    expect(JSON.parse(JSON.stringify(additionalData))).toStrictEqual({
      array_data: [3, 4, 5],
    })
  })
  test('updating a users additional data can set to false', () => {
    store.dispatch('auth/forceUpdateUserData', {
      active_licenses: { instance_wide: { premium: true } },
    })
    store.dispatch('auth/forceUpdateUserData', {
      active_licenses: {
        instance_wide: { premium: false },
      },
    })
    const additionalData = store.getters['auth/getAdditionalUserData']
    expect(JSON.parse(JSON.stringify(additionalData))).toStrictEqual({
      active_licenses: {
        instance_wide: { premium: false },
      },
    })
  })
})
