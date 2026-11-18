import { featureFlagIsEnabled } from '@baserow/modules/core/plugins/featureFlags'

const makeStore = (authenticated, additional) => ({
  getters: {
    'auth/isAuthenticated': authenticated,
    'auth/getAdditionalUserData': additional,
  },
})

describe('featureFlagIsEnabled', () => {
  test.each([
    ['enabled for the instance with *', ['*'], false, {}, true],
    ['enabled for the instance by name', ['test_flag'], false, {}, true],
    [
      'granted to the signed-in user',
      [''],
      true,
      { feature_flags: ['test_flag'] },
      true,
    ],
    [
      'not granted to the signed-in user',
      [''],
      true,
      { feature_flags: ['other'] },
      false,
    ],
    ['signed-in user without user flag data', [''], true, {}, false],
    [
      'granted to a user who signed out',
      [''],
      false,
      { feature_flags: ['test_flag'] },
      false,
    ],
  ])('%s', (_, instanceFlags, authenticated, additional, expected) => {
    const store = makeStore(authenticated, additional)

    expect(featureFlagIsEnabled(instanceFlags, 'TEST_FLAG', store)).toBe(
      expected
    )
  })
})
