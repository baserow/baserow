import { TestApp } from '@baserow/test/helpers/testApp'

describe('Notification store', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
    store.dispatch('notification/setWorkspace', { workspace: { id: 1 } })
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('can add an unread notification to current workspace increasing the unread counter', () => {
    store.dispatch('notification/forceCreateInBulk', {
      notifications: [
        {
          id: 1,
          type: 'test',
          workspace: { id: 1 },
          read: false,
        },
        {
          id: 2,
          type: 'test 2',
          workspace: { id: 1 },
          read: false,
        },
      ],
    })
    const notifications = store.getters['notification/getAll']
    expect(JSON.parse(JSON.stringify(notifications))).toStrictEqual([
      {
        id: 1,
        type: 'test',
        workspace: { id: 1 },
        read: false,
      },
      {
        id: 2,
        type: 'test 2',
        workspace: { id: 1 },
        read: false,
      },
    ])
    expect(store.getters['notification/getUnreadCount']).toBe(2)
    expect(store.getters['notification/anyOtherWorkspaceWithUnread']).toBe(
      false
    )
  })

  test('can add an already read notification to current workspace without increasing the unread counter', () => {
    store.dispatch('notification/forceCreateInBulk', {
      notifications: [
        {
          id: 1,
          type: 'test',
          workspace: { id: 1 },
          read: true,
        },
      ],
    })
    const notifications = store.getters['notification/getAll']
    expect(JSON.parse(JSON.stringify(notifications))).toStrictEqual([
      {
        id: 1,
        type: 'test',
        workspace: { id: 1 },
        read: true,
      },
    ])
    expect(store.getters['notification/getUnreadCount']).toBe(0)
    expect(store.getters['notification/anyOtherWorkspaceWithUnread']).toBe(
      false
    )
  })

  test('can add a notification to other workspace increasing relative unread counter', () => {
    store.dispatch('notification/forceCreateInBulk', {
      notifications: [
        {
          id: 1,
          type: 'test',
          workspace: { id: 999 },
          read: false,
        },
      ],
    })
    const notifications = store.getters['notification/getAll']
    expect(JSON.parse(JSON.stringify(notifications))).toStrictEqual([])
    expect(store.getters['notification/getUnreadCount']).toBe(0)
    expect(store.getters['notification/workspaceHasUnread'](999)).toBe(true)
    expect(store.getters['notification/anyOtherWorkspaceWithUnread']).toBe(true)
  })

  test('can mark a notification as read', () => {
    store.dispatch('notification/forceCreateInBulk', {
      notifications: [
        {
          id: 5,
          type: 'test',
          workspace: { id: 1 },
          read: false,
        },
      ],
    })
    store.dispatch('notification/forceMarkAsRead', { notification: { id: 5 } })

    const notifications = store.getters['notification/getAll']
    expect(JSON.parse(JSON.stringify(notifications))).toStrictEqual([
      {
        id: 5,
        type: 'test',
        workspace: { id: 1 },
        read: true,
      },
    ])

    expect(store.getters['notification/getUnreadCount']).toBe(0)
  })

  test('can mark all notifications as read', () => {
    store.commit('notification/SET', {
      notifications: [
        {
          id: 5,
          type: 'test',
          workspace: { id: 1 },
          read: false,
        },
        {
          id: 6,
          type: 'test 2',
          workspace: { id: 1 },
          read: false,
        },
      ],
    })
    store.commit('notification/SET_USER_UNREAD_COUNT', 999)
    expect(store.getters['notification/getUnreadCount']).toBe(999)

    store.dispatch('notification/forceMarkAllAsRead')

    const notifications = store.getters['notification/getAll']
    expect(JSON.parse(JSON.stringify(notifications))).toStrictEqual([
      {
        id: 5,
        type: 'test',
        workspace: { id: 1 },
        read: true,
      },
      {
        id: 6,
        type: 'test 2',
        workspace: { id: 1 },
        read: true,
      },
    ])
    expect(store.getters['notification/getUnreadCount']).toBe(0)
  })

  test('can clear all notifications', () => {
    store.commit('notification/SET', {
      notifications: [
        {
          id: 1,
          type: 'test',
          workspace: { id: 1 },
          read: true,
        },
        {
          id: 2,
          type: 'test',
          workspace: { id: 1 },
          read: false,
        },
      ],
    })

    store.dispatch('notification/forceClearAll')

    const notifications = store.getters['notification/getAll']
    expect(JSON.parse(JSON.stringify(notifications))).toStrictEqual([])
    expect(store.getters['notification/getUnreadCount']).toBe(0)
  })

  test('getting user data set the user unread count', async () => {
    const fakeUserData = {
      user: {
        id: 256,
      },
      access_token:
        `eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VybmFtZSI6ImpvaG5AZXhhb` +
        `XBsZS5jb20iLCJpYXQiOjE2NjAyOTEwODYsImV4cCI6MTY2MDI5NDY4NiwianRpIjo` +
        `iNDZmNzUwZWUtMTJhMS00N2UzLWJiNzQtMDIwYWM4Njg3YWMzIiwidXNlcl9pZCI6M` +
        `iwidXNlcl9wcm9maWxlX2lkIjpbMl0sIm9yaWdfaWF0IjoxNjYwMjkxMDg2fQ.RQ-M` +
        `NQdDR9zTi8CbbQkRrwNsyDa5CldQI83Uid1l9So`,
      user_notifications: { unread_count: 1 },
    }
    await store.dispatch('auth/setUserData', fakeUserData)

    expect(store.getters['notification/getUnreadCount']).toBe(1)
  })

  test('fetching workspaces set the unread count', async () => {
    await store.dispatch('notification/setPerWorkspaceUnreadCount', {
      workspaces: [
        { id: 1, unread_notifications_count: 1 },
        { id: 2, unread_notifications_count: 2 },
      ],
    })
    expect(store.getters['notification/getUnreadCount']).toBe(1)
    expect(store.getters['notification/workspaceHasUnread'](2)).toBe(true)
  })
})
