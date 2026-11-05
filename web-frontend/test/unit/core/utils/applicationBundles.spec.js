import { describe, expect, test, vi } from 'vitest'
import {
  isApplicationBundleLoaded,
  loadApplicationBundle,
  registerApplicationBundle,
} from '@baserow/modules/core/utils/applicationBundles'

describe('application feature bundles', () => {
  test('does not initialize unused applications', async () => {
    const app = {}
    const database = vi.fn(async () => ({ Database: {} }))
    const dashboard = vi.fn(async () => ({ Dashboard: {} }))
    registerApplicationBundle(app, 'database', database)
    registerApplicationBundle(app, 'dashboard', dashboard)
    expect(database).not.toHaveBeenCalled()
    expect(dashboard).not.toHaveBeenCalled()

    await loadApplicationBundle(app, 'dashboard')
    expect(dashboard).toHaveBeenCalledOnce()
    expect(database).not.toHaveBeenCalled()
    expect(isApplicationBundleLoaded(app, 'database')).toBe(false)
    expect(isApplicationBundleLoaded(app, 'dashboard')).toBe(true)
  })

  test('initializes base registrations before their extensions and merges UI exports', async () => {
    const app = { registrations: [] }
    const BaseComponent = {}
    const PremiumComponent = {}
    registerApplicationBundle(app, 'database', async (context) => {
      context.registrations.push('base')
      return { BaseComponent }
    })
    registerApplicationBundle(app, 'database', async (context) => {
      expect(context.registrations).toEqual(['base'])
      context.registrations.push('premium')
      return { PremiumComponent }
    })
    expect(await loadApplicationBundle(app, 'database')).toEqual({
      BaseComponent,
      PremiumComponent,
    })
    expect(app.registrations).toEqual(['base', 'premium'])
  })

  test('concurrent consumers initialize a feature once', async () => {
    const app = {}
    let finish
    const loader = vi.fn(
      () =>
        new Promise((resolve) => {
          finish = resolve
        })
    )
    registerApplicationBundle(app, 'database', loader)
    const first = loadApplicationBundle(app, 'database')
    const second = loadApplicationBundle(app, 'database')
    expect(loader).toHaveBeenCalledOnce()
    expect(isApplicationBundleLoaded(app, 'database')).toBe(false)
    finish({})
    await Promise.all([first, second])
    await loadApplicationBundle(app, 'database')
    expect(loader).toHaveBeenCalledOnce()
  })

  test('cached imports still register separately for each SSR application', async () => {
    const first = { registered: false }
    const second = { registered: false }
    const importedModule = {
      register: vi.fn((app) => {
        app.registered = true
      }),
    }
    for (const app of [first, second]) {
      registerApplicationBundle(app, 'database', async (context) => {
        importedModule.register(context)
        return importedModule
      })
    }
    await loadApplicationBundle(first, 'database')
    expect(first.registered).toBe(true)
    expect(second.registered).toBe(false)
    await loadApplicationBundle(second, 'database')
    expect(second.registered).toBe(true)
    expect(importedModule.register).toHaveBeenCalledTimes(2)
  })

  test('a failed feature does not become ready or prevent another feature loading', async () => {
    const app = {}
    registerApplicationBundle(app, 'database', async () => {
      throw new Error('chunk failed')
    })
    registerApplicationBundle(app, 'dashboard', async () => ({}))
    await expect(loadApplicationBundle(app, 'database')).rejects.toThrow(
      'chunk failed'
    )
    expect(isApplicationBundleLoaded(app, 'database')).toBe(false)
    await loadApplicationBundle(app, 'dashboard')
    expect(isApplicationBundleLoaded(app, 'dashboard')).toBe(true)
  })
})
