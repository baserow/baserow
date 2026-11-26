import {
  isAuthorCodeRestricted,
  isPreviewAuthorCodeRestricted,
  isPreviewSecurityRelaxed,
} from '@baserow/modules/builder/utils/authorCode'

describe('isPreviewSecurityRelaxed', () => {
  // The backend's str_to_bool reads exactly these as true.
  test.each([true, 'true', 'TRUE', ' true ', 1, '1', 'yes', 'y', 't', 'on'])(
    'is relaxed for %j',
    (value) => {
      expect(
        isPreviewSecurityRelaxed({
          builderDangerousRelaxPreviewSecurity: value,
        })
      ).toBe(true)
    }
  )

  // Nuxt leaves these as truthy strings, the backend reads them as false.
  test.each([
    false,
    'false',
    0,
    '0',
    '',
    undefined,
    null,
    'no',
    'off',
    'n',
    'f',
    'disabled',
    2,
  ])('stays restricted for %j', (value) => {
    expect(
      isPreviewSecurityRelaxed({ builderDangerousRelaxPreviewSecurity: value })
    ).toBe(false)
  })
})

describe('isAuthorCodeRestricted', () => {
  test.each([
    // The editor is always restricted.
    ['editing', true, false, true],
    ['editing', true, true, true],
    ['editing', false, true, true],
    // An application page on an editor hostname is restricted unless relaxed.
    ['preview', true, false, true],
    ['preview', true, true, false],
    ['public', true, false, true],
    ['public', true, true, false],
    // An unknown hostname counts as the editor's.
    ['preview', undefined, false, true],
    ['public', undefined, false, true],
    // An application on its own hostname is never restricted.
    ['preview', false, false, false],
    ['public', false, false, false],
    // An unknown mode is restricted.
    [undefined, false, true, true],
  ])(
    'mode %s on an editor hostname %s and relaxed %s: %s',
    (mode, onEditorHostname, relaxed, expected) => {
      expect(
        isAuthorCodeRestricted({
          mode,
          onEditorHostname,
          publicConfig: { builderDangerousRelaxPreviewSecurity: relaxed },
        })
      ).toBe(expected)
    }
  )

  test('a word the backend reads as false does not relax it', () => {
    expect(
      isAuthorCodeRestricted({
        mode: 'preview',
        onEditorHostname: true,
        publicConfig: { builderDangerousRelaxPreviewSecurity: 'no' },
      })
    ).toBe(true)
  })
})

describe('isPreviewAuthorCodeRestricted', () => {
  const editor = 'https://editor.example.com'

  test.each([
    [editor, false, true],
    [`${editor}:3001`, false, true],
    ['', false, true],
    [editor, true, false],
    ['https://preview.example.com', false, false],
    // An extra hostname of the editor is an editor hostname too.
    ['https://studio.example.com', false, true],
  ])(
    'Preview at %s and relaxed %s: %s',
    (builderPreviewUrl, relaxed, expected) => {
      expect(
        isPreviewAuthorCodeRestricted({
          builderPreviewUrl,
          publicWebFrontendUrl: editor,
          extraPublicWebFrontendHostnames: ['studio.example.com'],
          builderDangerousRelaxPreviewSecurity: relaxed,
        })
      ).toBe(expected)
    }
  )
})
