import { EnterprisePlugin } from '@baserow_enterprise/plugins'

describe('Test enterprise Baserow plugin', () => {
  const app = {
    $config: { public: { publicBackendUrl: 'http://localhost:8000' } },
  }

  const makeBuilder = (overrides = {}) => ({
    id: 42,
    scripts: [],
    custom_code: { css: '', js: '' },
    ...overrides,
  })

  // Regression test for the custom CSS/JS injection ordering. unhead v2 (pulled
  // in by the Nuxt 4 upgrade) dropped the legacy `body: true` flag, which caused
  // the custom stylesheet to render in <head> before the bundled theme CSS. With
  // equal specificity the theme then won on source order, forcing users to add
  // `!important` to their custom rules. The tags must use `tagPosition:
  // 'bodyClose'` so the custom CSS/JS renders last and wins the cascade tie.
  describe('getBuilderApplicationHeaderAddition', () => {
    test('custom CSS and JS are injected at body close', () => {
      const plugin = new EnterprisePlugin({ app })
      const builder = makeBuilder({
        custom_code: { css: '.ab-text { color: red }', js: 'console.log(1)' },
      })

      const { link, script } = plugin.getBuilderApplicationHeaderAddition({
        builder,
        mode: 'public',
      })

      const cssLink = link.find((l) => l.rel === 'stylesheet')
      expect(cssLink.tagPosition).toBe('bodyClose')
      expect(cssLink.body).toBeUndefined()

      const jsScript = script.find((s) => s.src.endsWith('/js/public/'))
      expect(jsScript.tagPosition).toBe('bodyClose')
      expect(jsScript.body).toBeUndefined()
    })

    test('external scripts and stylesheets are injected at body close', () => {
      const plugin = new EnterprisePlugin({ app })
      const builder = makeBuilder({
        scripts: [
          {
            type: 'javascript',
            url: 'https://example.com/a.js',
            load_type: 'defer',
          },
          { type: 'stylesheet', url: 'https://example.com/a.css' },
        ],
      })

      const { script } = plugin.getBuilderApplicationHeaderAddition({
        builder,
        mode: 'public',
      })

      expect(script).toHaveLength(2)
      script.forEach((tag) => {
        expect(tag.tagPosition).toBe('bodyClose')
        expect(tag.body).toBeUndefined()
      })
    })
  })
})
