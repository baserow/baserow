import { describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import {
  fetchPermissionsOfWorkspaces,
  getWorkspaceMembersCount,
} from '@baserow/modules/core/utils/workspace'

describe('workspace utils', () => {
  const workspace = {
    users: [{ id: 1 }],
    agents_count: 1,
  }

  test('includes agents when they are visible', () => {
    expect(getWorkspaceMembersCount(workspace, true)).toBe(2)
  })

  test('only includes users when agents are not visible', () => {
    expect(getWorkspaceMembersCount(workspace, false)).toBe(1)
  })
})

describe('fetchPermissionsOfWorkspaces', () => {
  // Every fetch stays pending until the test settles it.
  const createStore = () => {
    const fetches = []
    const store = {
      dispatch: vi.fn(
        (action, workspace) =>
          new Promise((resolve, reject) => {
            fetches.push({ action, workspace, resolve, reject })
          })
      ),
    }
    return { store, fetches }
  }

  const createWorkspaces = (count, loadedIds = []) =>
    Array.from({ length: count }, (_, index) => ({
      id: index + 1,
      _: { permissionsLoaded: loadedIds.includes(index + 1) },
    }))

  test('fetches three workspaces at a time', async () => {
    const { store, fetches } = createStore()
    const done = fetchPermissionsOfWorkspaces(store, createWorkspaces(5))

    await flushPromises()
    expect(fetches.map((fetch) => fetch.workspace.id)).toEqual([1, 2, 3])

    fetches[0].resolve()
    await flushPromises()
    expect(fetches.map((fetch) => fetch.workspace.id)).toEqual([1, 2, 3, 4])

    fetches.slice(1).forEach((fetch) => fetch.resolve())
    await flushPromises()
    fetches.slice(4).forEach((fetch) => fetch.resolve())
    await done
    expect(fetches).toHaveLength(5)
    expect(
      fetches.every((fetch) => fetch.action === 'workspace/fetchPermissions')
    ).toBe(true)
  })

  test('skips the workspaces that have their permissions', async () => {
    const { store, fetches } = createStore()
    const done = fetchPermissionsOfWorkspaces(
      store,
      createWorkspaces(3, [1, 3])
    )

    await flushPromises()
    expect(fetches.map((fetch) => fetch.workspace.id)).toEqual([2])
    fetches[0].resolve()
    await done
  })

  test('ignores a failed fetch', async () => {
    const { store, fetches } = createStore()
    const done = fetchPermissionsOfWorkspaces(store, createWorkspaces(2))

    await flushPromises()
    fetches[0].reject(new Error('Too many requests'))
    fetches[1].resolve()

    await expect(done).resolves.toHaveLength(2)
  })
})
