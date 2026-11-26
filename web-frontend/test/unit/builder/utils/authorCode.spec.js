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
    [true, false, true],
    [true, true, false],
    [undefined, false, true],
    [false, false, false],
    [false, true, false],
  ])(
    'on an editor hostname %s and relaxed %s: %s',
    (onEditorHostname, relaxed, expected) => {
      expect(
        isAuthorCodeRestricted({
          onEditorHostname,
          publicConfig: { builderDangerousRelaxPreviewSecurity: relaxed },
        })
      ).toBe(expected)
    }
  )

  test('a word the backend reads as false does not relax it', () => {
    expect(
      isAuthorCodeRestricted({
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
