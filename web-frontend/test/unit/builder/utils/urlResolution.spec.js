import { resolveFormula } from '@baserow/modules/core/formula'
import resolveElementUrl, {
  prefixInternalResolvedUrl,
  resolveBuilderUrl,
} from '@baserow/modules/builder/utils/urlResolution'

// Control characters are built with `String.fromCharCode` so they stay visible
// in the source instead of being invisible bytes in a string literal.
const chr = (code) => String.fromCharCode(code)

/**
 * Resolves a custom URL element for the given literal URL.
 */
const resolveCustomUrl = (
  url,
  editorMode = 'public',
  builder = { pages: [] }
) =>
  resolveElementUrl(
    {
      navigation_type: 'custom',
      navigate_to_url: { formula: `'${url.replace(/'/g, "\\'")}'` },
    },
    builder,
    builder.pages,
    resolveFormula,
    editorMode
  )

describe('resolveElementUrl tests', () => {
  test('Should return empty resolvedContext with page navigation type where page is not found.', () => {
    const element = {
      navigation_type: 'page',
      navigate_to_page_id: 42,
    }
    const builder = { pages: [{ id: 1 }] }

    const result = resolveElementUrl(
      element,
      builder,
      builder.pages,
      resolveFormula,
      'preview'
    )
    expect(result).toEqual('')
  })
  test('Should return resolvedContext with page navigation type where page is found and has no params.', () => {
    const element = {
      navigation_type: 'page',
      navigate_to_page_id: 1,
      page_parameters: [],
    }
    const builder = {
      id: 123,
      pages: [{ id: 1, path: '/contact-us/', path_params: [] }],
    }

    const result = resolveElementUrl(
      element,
      builder,
      builder.pages,
      resolveFormula,
      'preview'
    )
    expect(result).toEqual('/builder-preview/123/contact-us/')
  })
  test('Should not prefix published page navigation.', () => {
    const element = {
      navigation_type: 'page',
      navigate_to_page_id: 1,
      page_parameters: [],
    }
    const builder = {
      id: 123,
      pages: [{ id: 1, path: '/contact-us/', path_params: [] }],
    }

    const result = resolveElementUrl(
      element,
      builder,
      builder.pages,
      resolveFormula,
      'public'
    )
    expect(result).toEqual('/contact-us/')
  })
  test('Should return resolvedContext with page navigation type where page is found and has params.', () => {
    const element = {
      navigation_type: 'page',
      navigate_to_page_id: 1,
      page_parameters: [{ name: 'id', value: { formula: "'10'" } }],
    }
    const builder = {
      id: 123,
      pages: [
        {
          id: 1,
          path: '/product/:id/',
          path_params: [{ name: 'id', type: 'numeric' }],
        },
      ],
    }

    const result = resolveElementUrl(
      element,
      builder,
      builder.pages,
      resolveFormula,
      'preview'
    )
    expect(result).toEqual('/builder-preview/123/product/10/')
  })
  test('Should return resolvedContext for external custom navigation type.', () => {
    const element = {
      navigation_type: 'custom',
      navigate_to_url: { formula: "'https://baserow.io'" },
    }
    const builder = { pages: [] }

    const result = resolveElementUrl(
      element,
      builder,
      builder.pages,
      resolveFormula,
      'preview'
    )
    expect(result).toEqual('https://baserow.io')
  })
  test('Should return resolvedContext for internal custom navigation type.', () => {
    const element = {
      navigation_type: 'custom',
      navigate_to_url: { formula: "'/contact/'" },
    }
    const builder = { id: 123, pages: [] }

    const result = resolveElementUrl(
      element,
      builder,
      builder.pages,
      resolveFormula,
      'preview'
    )
    expect(result).toEqual('/builder-preview/123/contact/')
  })
  test('Should return resolvedContext and ignore element page params when destination page params are removed', () => {
    const element = {
      navigation_type: 'page',
      navigate_to_page_id: 1,
      page_parameters: [{ name: 'id', value: { formula: '"10"' } }],
    }
    const builder = {
      id: 123,
      pages: [{ id: 1, path: '/products/', path_params: [] }], // Page parameters have been removed
    }
    const result = resolveElementUrl(
      element,
      builder,
      builder.pages,
      resolveFormula,
      'preview'
    )
    expect(result).toEqual('/builder-preview/123/products/')
  })

  test.each([
    ['/?tab=one#details', '/builder-preview/123/?tab=one#details'],
    ['/builder-preview/123/page?tab=one', '/builder-preview/123/page?tab=one'],
  ])(
    'resolves preview queries, fragments, and existing URLs',
    (url, expected) => {
      expect(prefixInternalResolvedUrl(url, 'custom', 'preview', 123)).toBe(
        expected
      )
    }
  )

  test.each([
    [
      '/products?sort=name#list',
      'preview',
      123,
      '/builder-preview/123/products?sort=name#list',
    ],
    ['/products?sort=name#list', 'public', 123, '/products?sort=name#list'],
    [
      '/builder-preview/456/products',
      'preview',
      123,
      '/builder-preview/456/products',
    ],
    ['/', 'preview', 123, '/builder-preview/123/'],
  ])(
    'resolves logical builder URLs at the routing boundary',
    (path, mode, builderId, expected) => {
      expect(resolveBuilderUrl(path, mode, builderId)).toBe(expected)
    }
  )
})

describe('resolveElementUrl protocol guard tests', () => {
  // Browsers strip leading C0 control characters and spaces, and tab / LF / CR
  // from anywhere in a URL, before they read the scheme. Every payload below is
  // therefore `javascript:` or `data:` as far as the browser is concerned, and
  // must not be handed back to an `href`.
  test.each([
    ['no prefix', 'javascript:alert(1)'],
    ['leading space', ' javascript:alert(1)'],
    ['leading NULL', chr(0) + 'javascript:alert(1)'],
    ['leading SOH', chr(1) + 'javascript:alert(1)'],
    ['leading TAB', chr(9) + 'javascript:alert(1)'],
    ['leading LF', chr(10) + 'javascript:alert(1)'],
    ['leading CR', chr(13) + 'javascript:alert(1)'],
    ['leading US', chr(31) + 'javascript:alert(1)'],
    ['multiple leading characters', chr(1) + '  ' + 'javascript:alert(1)'],
    ['TAB inside the scheme', 'java' + chr(9) + 'script:alert(1)'],
    ['LF inside the scheme', 'java' + chr(10) + 'script:alert(1)'],
    ['uppercase scheme', 'JavaScript:alert(1)'],
    ['data url', chr(1) + 'data:text/html,<img src=x onerror=alert(1)>'],
  ])('Should block a disallowed protocol with %s.', (label, url) => {
    expect(resolveCustomUrl(url)).toEqual('')
  })

  test.each([
    ['https:', 'https://baserow.io'],
    ['http:', 'http://baserow.io'],
    ['mailto:', 'mailto:support@baserow.io'],
    ['tel:', 'tel:+3312345678'],
    ['ftpes:', 'ftpes://baserow.io'],
    ['an uppercase scheme', 'HTTPS://baserow.io'],
  ])('Should allow %s.', (label, url) => {
    expect(resolveCustomUrl(url)).toEqual(url)
  })

  test('Should strip leading characters from an allowed protocol.', () => {
    expect(resolveCustomUrl(chr(1) + ' https://baserow.io')).toEqual(
      'https://baserow.io'
    )
  })

  test('Should leave a relative URL untouched.', () => {
    expect(resolveCustomUrl('/contact/')).toEqual('/contact/')
  })

  test('Should not treat general Unicode whitespace as a prefix to strip.', () => {
    // Browsers do not strip U+00A0, so this genuinely is a relative path.
    expect(resolveCustomUrl(chr(160) + 'javascript:alert(1)')).toEqual(
      chr(160) + 'javascript:alert(1)'
    )
  })

  test('Should still prefix an internal URL with leading characters in preview.', () => {
    expect(
      resolveCustomUrl(' /contact/', 'preview', { id: 123, pages: [] })
    ).toEqual('/builder/123/preview/contact/')
  })
})
