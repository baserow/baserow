import { Registry, Registerable } from '@baserow/modules/core/registry'
import { computed, isReactive } from 'vue'

class FakeType extends Registerable {
  static getType() {
    return 'fake'
  }
}

describe('Registry domain loaders', () => {
  test('loadDomain runs each loader once and memoizes', async () => {
    const registry = new Registry()
    let calls = 0
    registry.registerDomainLoader('database', async () => {
      calls += 1
    })

    await Promise.all([
      registry.loadDomain('database'),
      registry.loadDomain('database'),
    ])
    await registry.loadDomain('database')

    expect(calls).toBe(1)
  })

  test('loaders run sequentially in registration order so overrides win by order', async () => {
    const registry = new Registry()
    registry.registerNamespace('dataSync')
    const order = []

    registry.registerDomainLoader('database', async () => {
      await Promise.resolve()
      order.push('core')
      registry.register('dataSync', new FakeType())
    })
    registry.registerDomainLoader('database', async () => {
      order.push('enterprise')
      registry.register('dataSync', new FakeType())
    })

    await registry.loadDomain('database')

    expect(order).toEqual(['core', 'enterprise'])
  })

  test('an unknown domain resolves without error', async () => {
    const registry = new Registry()
    await expect(registry.loadDomain('nope')).resolves.toBeUndefined()
  })

  test('retries a failed loader without replaying completed overrides', async () => {
    const registry = new Registry()
    registry.registerNamespace('field')
    const core = new FakeType()
    const enterprise = new FakeType()
    const order = []
    const coreLoader = vi.fn(() => {
      order.push('core')
      registry.register('field', core)
    })
    const premiumLoader = vi
      .fn()
      .mockRejectedValueOnce(new Error('Chunk unavailable'))
      .mockImplementation(() => order.push('premium'))
    const enterpriseLoader = vi.fn(() => {
      order.push('enterprise')
      registry.register('field', enterprise)
    })
    registry.registerDomainLoader('database', coreLoader)
    registry.registerDomainLoader('database', premiumLoader)
    registry.registerDomainLoader('database', enterpriseLoader)

    const first = registry.loadDomain('database')
    expect(registry.loadDomain('database')).toBe(first)
    await expect(first).rejects.toThrow('Chunk unavailable')
    expect(registry.isDomainLoaded('database')).toBe(false)
    expect(registry.get('field', 'fake')).toBe(core)

    await Promise.all([
      registry.loadDomain('database'),
      registry.loadDomain('database'),
    ])
    expect(coreLoader).toHaveBeenCalledTimes(1)
    expect(premiumLoader).toHaveBeenCalledTimes(2)
    expect(enterpriseLoader).toHaveBeenCalledTimes(1)
    expect(order).toEqual(['core', 'premium', 'enterprise'])
    expect(registry.get('field', 'fake')).toBe(enterprise)
    expect(registry.isDomainLoaded('database')).toBe(true)
  })

  test('a synchronous loader failure can retry', async () => {
    const registry = new Registry()
    const loader = vi.fn().mockImplementationOnce(() => {
      throw new Error('Failed registration')
    })
    registry.registerDomainLoader('builder', loader)

    await expect(registry.loadDomain('builder')).rejects.toThrow(
      'Failed registration'
    )
    await registry.loadDomain('builder')
    expect(loader).toHaveBeenCalledTimes(2)
  })

  test('a synchronous reentrant caller shares the in-flight promise', async () => {
    const registry = new Registry()
    let reentrant
    const loader = vi.fn(() => {
      reentrant = registry.loadDomain('database')
    })
    registry.registerDomainLoader('database', loader)

    const pending = registry.loadDomain('database')
    await pending
    expect(reentrant).toBe(pending)
    expect(loader).toHaveBeenCalledTimes(1)
  })

  test('loads extensions registered after an earlier successful load', async () => {
    const registry = new Registry()
    const core = vi.fn()
    const extension = vi.fn()
    registry.registerDomainLoader('database', core)
    await registry.loadDomain('database')

    registry.registerDomainLoader('database', extension)
    expect(registry.isDomainLoaded('database')).toBe(false)
    await registry.loadDomain('database')
    expect(core).toHaveBeenCalledTimes(1)
    expect(extension).toHaveBeenCalledTimes(1)
  })

  test('loading an unknown domain does not prevent later registrations', async () => {
    const registry = new Registry()
    await registry.loadDomain('extension')
    const loader = vi.fn()
    registry.registerDomainLoader('extension', loader)

    await registry.loadDomain('extension')
    expect(loader).toHaveBeenCalledTimes(1)
  })

  test('separate app registries do not share loading state', async () => {
    const first = new Registry()
    const second = new Registry()
    const loader = vi.fn()
    first.registerDomainLoader('database', loader)
    second.registerDomainLoader('database', loader)

    await first.loadDomain('database')
    expect(second.isDomainLoaded('database')).toBe(false)
    await second.loadDomain('database')
    expect(loader).toHaveBeenCalledTimes(2)
  })

  test('domain readiness updates computed consumers after every loader', async () => {
    const registry = new Registry()
    const ready = computed(() => registry.isDomainLoaded('database'))
    expect(ready.value).toBe(false)
    registry.registerDomainLoader('database', vi.fn())
    await registry.loadDomain('database')
    expect(ready.value).toBe(true)

    let finishExtension
    registry.registerDomainLoader(
      'database',
      () => new Promise((resolve) => (finishExtension = resolve))
    )
    expect(ready.value).toBe(false)
    const pending = registry.loadDomain('database')
    await Promise.resolve()
    expect(ready.value).toBe(false)
    finishExtension()
    await pending
    expect(ready.value).toBe(true)
  })

  test('computed type lists update while instances and app contexts stay raw', () => {
    const registry = new Registry()
    registry.registerNamespace('guidedTour')
    const types = computed(() => registry.getList('guidedTour'))
    expect(types.value).toEqual([])

    const app = { $store: {} }
    const type = new FakeType({ app })
    registry.register('guidedTour', type)
    expect(types.value).toEqual([type])
    expect(registry.get('guidedTour', 'fake')).toBe(type)
    expect(registry.get('guidedTour', 'fake').app).toBe(app)
    expect(isReactive(type)).toBe(false)
    expect(isReactive(type.app)).toBe(false)

    registry.unregister('guidedTour', 'fake')
    expect(types.value).toEqual([])
  })
})
