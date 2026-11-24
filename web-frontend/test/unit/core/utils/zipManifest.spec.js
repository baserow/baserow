import { manifestHasIdentities } from '@baserow/modules/core/utils/zipManifest'

describe('manifestHasIdentities', () => {
  test.each([
    [null, false],
    [{}, false],
    [{ workspace_objects: null }, false],
    [{ workspace_objects: { identities: 'x' } }, false],
    [{ workspace_objects: { identities: [] } }, false],
    [{ workspace_objects: { identities: [{ key: 'a' }] } }, true],
  ])('reads the identities of %j as %s', (manifest, expected) => {
    expect(manifestHasIdentities(manifest)).toBe(expected)
  })
})
