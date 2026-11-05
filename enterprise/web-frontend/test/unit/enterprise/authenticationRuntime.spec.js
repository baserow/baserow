import { describe, expect, test } from 'vitest'
import { Registry } from '@baserow/modules/core/registry'
import registerAuthentication from '@baserow_enterprise/pluginAuthentication'

describe('enterprise authentication startup', () => {
  test('registers sign-in providers and license metadata without application features', async () => {
    const registry = new Registry()
    registry.registerNamespace('authProvider')
    registry.registerNamespace('license')
    await registerAuthentication({ $registry: registry })

    expect(Object.keys(registry.getAll('authProvider')).sort()).toEqual([
      'facebook',
      'github',
      'gitlab',
      'google',
      'openid_connect',
      'password',
      'saml',
    ])
    expect(Object.keys(registry.getAll('license')).length).toBe(3)
    expect(Object.keys(registry.registry).sort()).toEqual([
      'authProvider',
      'license',
    ])
  })
})
