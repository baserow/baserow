import { Registry, Registerable } from '@baserow/modules/core/registry'

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
})
