// The test app is served on the editor's hostname, like a default install.
describe('author code plugin', () => {
  let publicConfig
  let original

  beforeEach(() => {
    publicConfig = useRuntimeConfig().public
    original = {
      builderPreviewUrl: publicConfig.builderPreviewUrl,
      publicWebFrontendUrl: publicConfig.publicWebFrontendUrl,
      builderDangerousRelaxPreviewSecurity:
        publicConfig.builderDangerousRelaxPreviewSecurity,
    }
  })

  afterEach(() => {
    Object.assign(publicConfig, original)
  })

  test.each([
    ['editing', false, true],
    ['editing', true, true],
    ['preview', false, true],
    ['preview', true, false],
    ['public', false, true],
    ['public', true, false],
  ])(
    'in %s mode with relaxed security %s, author code is restricted: %s',
    (mode, relaxed, expected) => {
      publicConfig.builderDangerousRelaxPreviewSecurity = relaxed

      expect(useNuxtApp().$isAuthorCodeRestricted(mode)).toBe(expected)
    }
  )

  test.each([
    ['http://localhost:3001', false, true],
    ['http://localhost:3001', true, false],
    ['http://preview.localhost:3000', false, false],
  ])(
    'with Preview at %s and relaxed security %s, Preview restricts author code: %s',
    (builderPreviewUrl, relaxed, expected) => {
      Object.assign(publicConfig, {
        builderPreviewUrl,
        publicWebFrontendUrl: 'http://localhost:3000',
        builderDangerousRelaxPreviewSecurity: relaxed,
      })

      expect(useNuxtApp().$previewRestrictsAuthorCode()).toBe(expected)
    }
  )
})
