import { fetchWorkspacesAndApplications } from '@baserow/modules/core/utils/workspace'

const deferred = () => {
  let resolve
  let reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const makeApp = () => ({
  $store: {
    getters: {
      'workspace/isLoaded': false,
      'workspace/getAll': [{ id: 1 }],
      'application/isLoaded': false,
    },
    dispatch: vi.fn().mockResolvedValue(undefined),
  },
})

describe('Workspace and application bootstrap', () => {
  test('loads applications while selecting the route workspace and waits for both', async () => {
    const app = makeApp()
    const selection = deferred()
    const applications = deferred()
    app.$store.dispatch.mockImplementation((action) => {
      if (action === 'workspace/selectById') return selection.promise
      if (action === 'application/fetchAll') return applications.promise
      return Promise.resolve()
    })
    let ready = false
    const bootstrap = fetchWorkspacesAndApplications(app, 1).then(() => {
      ready = true
    })
    await Promise.resolve()
    expect(app.$store.dispatch).toHaveBeenCalledWith('workspace/selectById', 1)
    expect(app.$store.dispatch).toHaveBeenCalledWith('application/fetchAll')
    applications.resolve()
    await Promise.resolve()
    expect(ready).toBe(false)
    selection.resolve()
    await bootstrap
    expect(ready).toBe(true)
  })

  test('preserves application loading when workspace selection is denied', async () => {
    const app = makeApp()
    app.$store.dispatch.mockImplementation((action) =>
      action === 'workspace/selectById'
        ? Promise.reject(new Error('Permission denied'))
        : Promise.resolve()
    )
    await expect(
      fetchWorkspacesAndApplications(app, 1)
    ).resolves.toBeUndefined()
    expect(app.$store.dispatch).toHaveBeenCalledWith('application/fetchAll')
  })

  test('propagates application loading failures', async () => {
    const app = makeApp()
    app.$store.dispatch.mockImplementation((action) =>
      action === 'application/fetchAll'
        ? Promise.reject(new Error('Network error'))
        : Promise.resolve()
    )
    await expect(fetchWorkspacesAndApplications(app, 1)).rejects.toThrow(
      'Network error'
    )
  })

  test.each([null, 99])(
    'does not select an unrelated workspace for route %s',
    async (id) => {
      const app = makeApp()
      await fetchWorkspacesAndApplications(app, id)
      expect(app.$store.dispatch).not.toHaveBeenCalledWith(
        'workspace/selectById',
        expect.anything()
      )
      expect(app.$store.dispatch).toHaveBeenCalledWith('application/fetchAll')
    }
  )

  test('does not refetch already loaded workspaces or applications', async () => {
    const app = makeApp()
    app.$store.getters['workspace/isLoaded'] = true
    app.$store.getters['application/isLoaded'] = true
    await fetchWorkspacesAndApplications(app, 1)
    expect(app.$store.dispatch).not.toHaveBeenCalled()
  })
})
