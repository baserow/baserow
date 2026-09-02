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

  test('updating user preferences is optimistic and merges the response', async () => {
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

  test('updating user preferences rolls back to the confirmed value', async () => {
    store.dispatch('auth/forceSetUserData', {
      ...fakeUserData,
      user: { id: 256, preferences: { sort: 'created' } },
    })
    testApp.mock.onPatch('/user/preferences/').reply(400, {
      error: 'ERROR_REQUEST_BODY_VALIDATION',
    })

    await expect(
      store.dispatch('auth/updateUserPreferences', { sort: 'bogus' })
    ).rejects.toBeTruthy()
    expect(store.getters['auth/getUserPreference']('sort')).toBe('created')
  })

  test('preference writes are sent in order and superseded ones skipped', async () => {
    store.dispatch('auth/forceSetUserData', {
      ...fakeUserData,
      user: { id: 256, preferences: { sort: 'created' } },
    })
    testApp.mock.onPatch('/user/preferences/').reply((config) => {
      return [200, JSON.parse(config.data)]
    })

    const first = store.dispatch('auth/updateUserPreferences', {
      sort: 'name_asc',
    })
    const second = store.dispatch('auth/updateUserPreferences', {
      sort: 'name_desc',
    })
    expect(store.getters['auth/getUserPreference']('sort')).toBe('name_desc')
    await Promise.all([first, second])

    // The first change was superseded before it was sent.
    expect(testApp.mock.history.patch.map((r) => r.data)).toEqual([
      JSON.stringify({ sort: 'name_desc' }),
    ])
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
