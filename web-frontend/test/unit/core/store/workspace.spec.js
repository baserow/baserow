import workspaceStore from '@baserow/modules/core/store/workspace'
import authStore from '@baserow/modules/core/store/auth'
import { TestApp } from '@baserow/test/helpers/testApp'
import { expect, test } from 'vitest'

describe('Workspace store', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.createStore({
      modules: {
        workspace: workspaceStore,
        auth: authStore,
      },
    })
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('forceAddWorkspaceUser adds user to a workspace', async () => {
    const state = Object.assign(workspaceStore.state(), {
      items: [
        {
          id: 1,
          name: 'Workspace 1',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 73,
              user_id: 256,
              workspace: 1,
              name: 'John',
              email: 'john@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
      ],
    })
    store.replaceState({ ...store.state, workspace: state })

    await store.dispatch('workspace/forceAddWorkspaceUser', {
      workspaceId: 1,
      values: {
        id: 74,
        user_id: 257,
        workspace: 1,
        name: 'Adam',
        email: 'adam@example.com',
        permissions: 'MEMBER',
        to_be_deleted: false,
        created_on: '2022-08-10T14:20:05.629890Z',
      },
    })

    const workspace = store.getters['workspace/get'](1)
    expect(workspace.users.length).toBe(2)
    expect(workspace.users[1].user_id).toBe(257)
    expect(workspace.users[1].permissions).toBe('MEMBER')
  })

  test('forceUpdateWorkspaceUser updates a user from the workspace', async () => {
    const state = Object.assign(workspaceStore.state(), {
      items: [
        {
          id: 1,
          name: 'Workspace 1',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 73,
              user_id: 256,
              workspace: 1,
              name: 'John',
              email: 'john@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
      ],
    })
    store.replaceState({ ...store.state, workspace: state })

    await store.dispatch('workspace/forceUpdateWorkspaceUser', {
      workspaceId: 1,
      id: 73,
      values: {
        id: 73,
        user_id: 256,
        workspace: 1,
        name: 'Petr',
        email: 'petr@example.com',
        permissions: 'MEMBER',
        to_be_deleted: false,
        created_on: '2022-08-10T14:20:05.629890Z',
      },
    })

    const workspace = store.getters['workspace/get'](1)
    expect(workspace.users.length).toBe(1)
    expect(workspace.users[0].name).toBe('Petr')
    expect(workspace.users[0].permissions).toBe('MEMBER')
  })

  test(`forceUpdateWorkspaceUser updates a current workspace permissions
        when the current user is updated`, async () => {
    await store.dispatch('auth/forceSetUserData', {
      user: {
        id: 256,
      },
      access_token:
        `eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VybmFtZSI6ImpvaG5AZXhhb` +
        `XBsZS5jb20iLCJpYXQiOjE2NjAyOTEwODYsImV4cCI6MTY2MDI5NDY4NiwianRpIjo` +
        `iNDZmNzUwZWUtMTJhMS00N2UzLWJiNzQtMDIwYWM4Njg3YWMzIiwidXNlcl9pZCI6M` +
        `iwidXNlcl9wcm9maWxlX2lkIjpbMl0sIm9yaWdfaWF0IjoxNjYwMjkxMDg2fQ.RQ-M` +
        `NQdDR9zTi8CbbQkRrwNsyDa5CldQI83Uid1l9So`,
    })

    const state = Object.assign(workspaceStore.state(), {
      items: [
        {
          id: 1,
          name: 'Workspace 1',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 73,
              user_id: 256,
              workspace: 1,
              name: 'John',
              email: 'john@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
      ],
    })
    store.replaceState({ ...store.state, workspace: state })

    await store.dispatch('workspace/forceUpdateWorkspaceUser', {
      workspaceId: 1,
      id: 73,
      values: {
        id: 73,
        user_id: 256,
        workspace: 1,
        name: 'Petr',
        email: 'petr@example.com',
        permissions: 'MEMBER',
        to_be_deleted: false,
        created_on: '2022-08-10T14:20:05.629890Z',
      },
    })

    const workspace = store.getters['workspace/get'](1)
    expect(workspace.users.length).toBe(1)
    expect(workspace.users[0].name).toBe('Petr')
    expect(workspace.users[0].permissions).toBe('MEMBER')

    expect(workspace.permissions).toBe('MEMBER')
  })

  test('forceUpdateWorkspaceUserAttributes updates a user across all workspaces', async () => {
    const state = Object.assign(workspaceStore.state(), {
      items: [
        {
          id: 1,
          name: 'Workspace 1',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 73,
              user_id: 256,
              workspace: 1,
              name: 'John',
              email: 'john@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
        {
          id: 2,
          name: 'Workspace 2',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 2136,
              user_id: 456,
              workspace: 2,
              name: 'Peter',
              email: 'peter@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
            {
              id: 173,
              user_id: 256,
              workspace: 2,
              name: 'John',
              email: 'john@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
        {
          id: 3,
          name: 'Workspace 3',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 2132,
              user_id: 456,
              workspace: 3,
              name: 'Peter',
              email: 'peter@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
      ],
    })

    store.replaceState({ ...store.state, workspace: state })

    await store.dispatch('workspace/forceUpdateWorkspaceUserAttributes', {
      userId: 256,
      values: {
        name: 'John renamed',
        to_be_deleted: true,
      },
    })

    const workspace = store.getters['workspace/get'](1)
    expect(workspace.users[0].name).toBe('John renamed')
    expect(workspace.users[0].to_be_deleted).toBe(true)

    const workspace2 = store.getters['workspace/get'](2)
    expect(workspace2.users[0].name).toBe('Peter')
    expect(workspace2.users[0].to_be_deleted).toBe(false)
    expect(workspace2.users[1].name).toBe('John renamed')
    expect(workspace2.users[1].to_be_deleted).toBe(true)

    const workspace3 = store.getters['workspace/get'](3)
    expect(workspace3.users[0].name).toBe('Peter')
    expect(workspace3.users[0].to_be_deleted).toBe(false)
  })

  test('forceDeleteWorkspaceUser removes a user from the workspace', async () => {
    const state = Object.assign(workspaceStore.state(), {
      items: [
        {
          id: 1,
          name: 'Workspace 1',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 73,
              user_id: 256,
              workspace: 1,
              name: 'John',
              email: 'john@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
      ],
    })

    store.replaceState({ ...store.state, workspace: state })

    await store.dispatch('workspace/forceDeleteWorkspaceUser', {
      workspaceId: 1,
      id: 73,
      values: {
        id: 73,
        user_id: 256,
        workspace: 1,
        name: 'John',
        email: 'john@example.com',
        permissions: 'ADMIN',
        to_be_deleted: false,
        created_on: '2022-08-10T14:20:05.629890Z',
      },
    })

    const workspace = store.getters['workspace/get'](1)
    expect(workspace.users.length).toBe(0)
  })

  test(`forceDeleteWorkspaceUser removes the whole workspace if the
        current user is being removed`, async () => {
    await store.dispatch('auth/forceSetUserData', {
      user: {
        id: 256,
      },
      access_token:
        `eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VybmFtZSI6ImpvaG5AZXhhb` +
        `XBsZS5jb20iLCJpYXQiOjE2NjAyOTEwODYsImV4cCI6MTY2MDI5NDY4NiwianRpIjo` +
        `iNDZmNzUwZWUtMTJhMS00N2UzLWJiNzQtMDIwYWM4Njg3YWMzIiwidXNlcl9pZCI6M` +
        `iwidXNlcl9wcm9maWxlX2lkIjpbMl0sIm9yaWdfaWF0IjoxNjYwMjkxMDg2fQ.RQ-M` +
        `NQdDR9zTi8CbbQkRrwNsyDa5CldQI83Uid1l9So`,
    })

    const state = Object.assign(workspaceStore.state(), {
      items: [
        {
          id: 1,
          name: 'Workspace 1',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 73,
              user_id: 256,
              workspace: 1,
              name: 'John',
              email: 'john@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
      ],
    })

    store.replaceState({ ...store.state, workspace: state })

    await store.dispatch('workspace/forceDeleteWorkspaceUser', {
      workspaceId: 1,
      id: 73,
      values: {
        id: 73,
        user_id: 256,
        workspace: 1,
        name: 'John',
        email: 'john@example.com',
        permissions: 'ADMIN',
        to_be_deleted: false,
        created_on: '2022-08-10T14:20:05.629890Z',
      },
    })

    const workspaces = store.getters['workspace/getAll']
    expect(workspaces.length).toBe(0)
  })

  test('forceDeleteUser deletes all workspace users across all workspaces', async () => {
    const state = {
      ...workspaceStore.state(),
      items: [
        {
          id: 1,
          name: 'Workspace 1',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 73,
              user_id: 256,
              workspace: 1,
              name: 'John',
              email: 'john@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
        {
          id: 2,
          name: 'Workspace 2',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 2136,
              user_id: 456,
              workspace: 2,
              name: 'Peter',
              email: 'peter@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
            {
              id: 173,
              user_id: 256,
              workspace: 2,
              name: 'John',
              email: 'john@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
        {
          id: 3,
          name: 'Workspace 3',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 2132,
              user_id: 456,
              workspace: 3,
              name: 'Peter',
              email: 'peter@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
      ],
    }

    store.replaceState({ ...store.state, workspace: state })

    await store.dispatch('workspace/forceDeleteUser', {
      userId: 256,
    })

    const workspace = store.getters['workspace/get'](1)
    expect(workspace.users.length).toBe(0)

    const workspace2 = store.getters['workspace/get'](2)
    expect(workspace2.users[0].name).toBe('Peter')
    expect(workspace2.users[0].to_be_deleted).toBe(false)
    expect(workspace2.users.length).toBe(1)

    const workspace3 = store.getters['workspace/get'](3)
    expect(workspace3.users.length).toBe(1)
  })

  test('getAllUsers collects users from all workspaces', async () => {
    const state = Object.assign(workspaceStore.state(), {
      items: [
        {
          id: 1,
          name: 'Workspace 1',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 73,
              user_id: 256,
              workspace: 1,
              name: 'John',
              email: 'john@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
        {
          id: 2,
          name: 'Workspace 2',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 2136,
              user_id: 456,
              workspace: 2,
              name: 'Peter',
              email: 'peter@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
            {
              id: 173,
              user_id: 256,
              workspace: 2,
              name: 'John',
              email: 'john@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
        {
          id: 3,
          name: 'Workspace 3',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 2144,
              user_id: 556,
              workspace: 3,
              name: 'Mark',
              email: 'mark@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
      ],
    })

    store.replaceState({ ...store.state, workspace: state })

    const allUsers = await store.getters['workspace/getAllUsers']
    expect(allUsers[256].name).toBe('John')
    expect(allUsers[456].name).toBe('Peter')
    expect(allUsers[556].name).toBe('Mark')
  })

  test('getAllUsersByEmail collects users by email from all workspaces', async () => {
    const state = Object.assign(workspaceStore.state(), {
      items: [
        {
          id: 1,
          name: 'Workspace 1',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 73,
              user_id: 256,
              workspace: 1,
              name: 'John',
              email: 'john@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
        {
          id: 2,
          name: 'Workspace 2',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 2136,
              user_id: 456,
              workspace: 2,
              name: 'Peter',
              email: 'peter@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
            {
              id: 173,
              user_id: 256,
              workspace: 2,
              name: 'John',
              email: 'john@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
        {
          id: 3,
          name: 'Workspace 3',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 2144,
              user_id: 556,
              workspace: 3,
              name: 'Mark',
              email: 'mark@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
      ],
    })

    store.replaceState({ ...store.state, workspace: state })

    const allUsers = await store.getters['workspace/getAllUsersByEmail']
    expect(allUsers['john@example.com'].name).toBe('John')
    expect(allUsers['peter@example.com'].name).toBe('Peter')
    expect(allUsers['mark@example.com'].name).toBe('Mark')
  })

  test('getUserById returns user by id from any of the workspaces', async () => {
    const state = Object.assign(workspaceStore.state(), {
      items: [
        {
          id: 1,
          name: 'Workspace 1',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 73,
              user_id: 256,
              workspace: 1,
              name: 'John',
              email: 'john@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
        {
          id: 2,
          name: 'Workspace 2',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 2136,
              user_id: 456,
              workspace: 2,
              name: 'Peter',
              email: 'peter@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
            {
              id: 173,
              user_id: 256,
              workspace: 2,
              name: 'John',
              email: 'john@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
        {
          id: 3,
          name: 'Workspace 3',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 2144,
              user_id: 556,
              workspace: 3,
              name: 'Mark',
              email: 'mark@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
      ],
    })

    store.replaceState({ ...store.state, workspace: state })

    const mark = await store.getters['workspace/getUserById'](556)
    expect(mark.name).toBe('Mark')
  })

  test('getUserByEmail returns user by email from any of the workspaces', async () => {
    const state = Object.assign(workspaceStore.state(), {
      items: [
        {
          id: 1,
          name: 'Workspace 1',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 73,
              user_id: 256,
              workspace: 1,
              name: 'John',
              email: 'john@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
        {
          id: 2,
          name: 'Workspace 2',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 2136,
              user_id: 456,
              workspace: 2,
              name: 'Peter',
              email: 'peter@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
            {
              id: 173,
              user_id: 256,
              workspace: 2,
              name: 'John',
              email: 'john@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
        {
          id: 3,
          name: 'Workspace 3',
          order: 1,
          permissions: 'ADMIN',
          users: [
            {
              id: 2144,
              user_id: 556,
              workspace: 3,
              name: 'Mark',
              email: 'mark@example.com',
              permissions: 'ADMIN',
              to_be_deleted: false,
              created_on: '2022-08-10T14:20:05.629890Z',
            },
          ],
        },
      ],
    })

    store.replaceState({ ...store.state, workspace: state })

    const mark =
      await store.getters['workspace/getUserByEmail']('mark@example.com')
    expect(mark.name).toBe('Mark')
  })
})
