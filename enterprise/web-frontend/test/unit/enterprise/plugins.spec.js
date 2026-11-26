import { EnterprisePlugin } from '@baserow_enterprise/plugins'
import { isAuthorCodeRestricted } from '@baserow/modules/builder/utils/authorCode'
import AssistantPanel from '@baserow_enterprise/components/assistant/AssistantPanel'

describe('Test enterprise Baserow plugin', () => {
  const app = {
    // Applications are served on their own hostname unless a test says otherwise.
    $isAuthorCodeRestricted: () =>
      isAuthorCodeRestricted({
        onEditorHostname: false,
        publicConfig: {},
      }),
    $config: {
      public: {
        publicBackendUrl: 'http://localhost:8000',
        publicWebFrontendUrl: 'http://localhost:3000',
        builderPreviewUrl: 'http://preview.localhost:3000',
      },
    },
  }

  const makeBuilder = (overrides = {}) => ({
    id: 42,
    scripts: [],
    custom_code: { css: '', js: '' },
    ...overrides,
  })

  test('only mounts the assistant panel where Kuma is effectively enabled', () => {
    const plugin = new EnterprisePlugin({ app })

    expect(
      plugin.getRightSidebarWorkspaceComponents({
        ai_features: { kuma: { is_enabled: true } },
      })
    ).toEqual([AssistantPanel])
    expect(
      plugin.getRightSidebarWorkspaceComponents({
        ai_features: { kuma: { is_enabled: false } },
      })
    ).toEqual([])
  })

  describe('canCreateScopedIdentities', () => {
    const workspace = { id: 7 }
    const OPERATIONS = ['identity.create_scoped', 'identity.bind']

    const pluginWith = ({ rbac = true, denied = null } = {}) =>
      new EnterprisePlugin({
        app: {
          ...app,
          $hasFeature: (feature, workspaceId) =>
            rbac && feature === 'RBAC' && workspaceId === workspace.id,
          $hasPermission: (operation) => operation !== denied,
        },
      })

    test('needs roles and the permissions to create and bind scoped identities', () => {
      expect(pluginWith().canCreateScopedIdentities(workspace)).toBe(true)
      expect(
        pluginWith({ rbac: false }).canCreateScopedIdentities(workspace)
      ).toBe(false)
      for (const denied of OPERATIONS) {
        expect(
          pluginWith({ denied }).canCreateScopedIdentities(workspace)
        ).toBe(false)
      }
    })
  })

  // Regression test for the custom CSS/JS injection ordering. unhead v2 (pulled
  // in by the Nuxt 4 upgrade) dropped the legacy `body: true` flag, which caused
  // the custom stylesheet to render in <head> before the bundled theme CSS. With
  // equal specificity the theme then won on source order, forcing users to add
  // `!important` to their custom rules. The tags must use `tagPosition:
  // 'bodyClose'` so the custom CSS/JS renders last and wins the cascade tie.
  describe('getBuilderApplicationHeaderAddition', () => {
    test.each(['preview', 'public'])(
      'blocks all custom code and external assets in %s until trusted',
      (mode) => {
        const plugin = new EnterprisePlugin({ app })
        const builder = makeBuilder({
          untrusted_content: true,
          custom_code: { css: 'body { color: red }', js: 'alert(1)' },
          scripts: [
            { type: 'javascript', url: 'https://example.com/a.js' },
            { type: 'stylesheet', url: 'https://example.com/a.css' },
          ],
        })
        expect(
          plugin.getBuilderApplicationHeaderAddition({ builder, mode })
        ).toMatchSnapshot()
        builder.untrusted_content = false
        const { link, script } = plugin.getBuilderApplicationHeaderAddition({
          builder,
          mode,
        })
        expect(link).toHaveLength(1)
        expect(script).toHaveLength(3)
      }
    )

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

    test('preview custom CSS and JS include preview credentials', () => {
      const plugin = new EnterprisePlugin({ app })
      const builder = makeBuilder({
        custom_code: { css: '.ab-text { color: red }', js: 'console.log(1)' },
      })

      const { link, script } = plugin.getBuilderApplicationHeaderAddition({
        builder,
        mode: 'preview',
      })

      expect(link[0].crossorigin).toBe('use-credentials')
      expect(link[0].href).toBe(
        'http://localhost:8000/api/builder/preview/42/custom-code/css/'
      )
      expect(script[0].crossorigin).toBe('use-credentials')
      expect(script[0].src).toBe(
        'http://localhost:8000/api/builder/preview/42/custom-code/js/'
      )
    })

    test.each([
      ['preview', true, false, false],
      ['preview', true, true, true],
      ['preview', false, false, true],
      // The editor's hostname also serves published applications by id.
      ['public', true, false, false],
      ['public', false, false, true],
    ])(
      'in %s on an editor hostname %s and relaxed security %s, JavaScript loads: %s',
      (mode, onEditorHostname, relaxed, runsJS) => {
        const plugin = new EnterprisePlugin({
          app: {
            ...app,
            $isAuthorCodeRestricted: () =>
              isAuthorCodeRestricted({
                onEditorHostname,
                publicConfig: { builderDangerousRelaxPreviewSecurity: relaxed },
              }),
          },
        })
        const builder = makeBuilder({
          custom_code: { css: 'body { color: red }', js: 'alert(1)' },
          scripts: [
            { type: 'javascript', url: 'https://example.com/a.js' },
            { type: 'stylesheet', url: 'https://example.com/a.css' },
          ],
        })

        const { link, script } = plugin.getBuilderApplicationHeaderAddition({
          builder,
          mode,
        })

        expect(link.map(({ href }) => href)).toEqual([
          mode === 'preview'
            ? 'http://localhost:8000/api/builder/preview/42/custom-code/css/'
            : 'http://localhost:8000/api/custom_code/42/css/public/',
        ])
        expect(script.map(({ src, href }) => src ?? href)).toEqual(
          runsJS
            ? [
                'https://example.com/a.js',
                'https://example.com/a.css',
                expect.stringMatching(/\/js\/(public\/)?$/),
              ]
            : ['https://example.com/a.css']
        )
      }
    )

    test.each([
      [{ custom_code: { css: '', js: 'alert(1)' } }, true],
      [{ has_head_html: true }, true],
      [{ scripts: [{ type: 'javascript', url: 'https://x.test/a.js' }] }, true],
      [
        { scripts: [{ type: 'stylesheet', url: 'https://x.test/a.css' }] },
        false,
      ],
      [{ custom_code: { css: 'body {}', js: '' } }, false],
      [
        { custom_code: { css: '', js: 'alert(1)' }, untrusted_content: true },
        false,
      ],
    ])('knows whether %j adds author code: %s', (overrides, expected) => {
      const plugin = new EnterprisePlugin({ app })

      expect(
        plugin.hasBuilderAuthorCode({ builder: makeBuilder(overrides) })
      ).toBe(expected)
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
