import { fetchBuilderHeadHtml } from '@baserow_enterprise/plugins/builderHeadHtml.server'

describe('Fetching Custom Code HTML during a Builder render', () => {
  const builder = { id: 42, has_head_html: true }
  const config = {
    privateBackendUrl: 'http://backend:8000',
    public: {
      publicWebFrontendUrl: 'https://editor.example.com',
      builderPreviewUrl: 'https://preview.example.com',
    },
  }
  const previewOptions = {
    builder,
    config,
    mode: 'preview',
    // What `$isAuthorCodeRestricted(mode)` answers for this page.
    restricted: false,
    previewSsrCookieHeader: 'test_baserow_builder_preview=signed-session',
    requestUrl: new URL('https://preview.example.com/builder/preview/42'),
  }

  test.each([
    ['public', 'custom_code/42/html/public/', { Accept: 'application/json' }],
    [
      'preview',
      'builder/preview/42/custom-code/html/',
      {
        Accept: 'application/json',
        Cookie: previewOptions.previewSsrCookieHeader,
      },
    ],
  ])(
    'fetches the %s fragment verbatim with scoped credentials',
    async (mode, path, headers) => {
      const html = '\n<meta name="description" content="Baserow">\n'
      const fetch = vi.fn().mockResolvedValue({ html })

      expect(
        await fetchBuilderHeadHtml({ ...previewOptions, mode }, fetch)
      ).toBe(html)
      expect(fetch).toHaveBeenCalledWith(
        path,
        expect.objectContaining({
          baseURL: 'http://backend:8000/api/',
          headers,
        })
      )
    }
  )

  test.each([
    ['untrusted content', { builder: { ...builder, untrusted_content: true } }],
    ['empty content', { builder: { id: 42, has_head_html: false } }],
    ['no Preview session', { previewSsrCookieHeader: undefined }],
    [
      'a different request origin',
      { requestUrl: new URL('https://other.example.com') },
    ],
    ['Marketplace preview', { mode: 'template' }],
    [
      'same editor and Preview hostname on different ports',
      {
        config: {
          ...config,
          public: {
            ...config.public,
            builderPreviewUrl: 'https://editor.example.com:444',
          },
        },
        requestUrl: new URL(
          'https://editor.example.com:444/builder/preview/42'
        ),
        restricted: true,
      },
    ],
    [
      'a published application with restricted author code',
      { mode: 'public', restricted: true },
    ],
    ['an unknown restriction', { restricted: undefined }],
  ])('skips requests for %s', async (_, overrides) => {
    const fetch = vi.fn()

    expect(
      await fetchBuilderHeadHtml({ ...previewOptions, ...overrides }, fetch)
    ).toBe('')
    expect(fetch).not.toHaveBeenCalled()
  })

  test('fetches on the editor hostname when author code is not restricted', async () => {
    const fetch = vi.fn().mockResolvedValue({ html: '<meta name="x">' })

    expect(
      await fetchBuilderHeadHtml(
        {
          ...previewOptions,
          config: {
            ...config,
            public: {
              ...config.public,
              builderPreviewUrl: 'https://editor.example.com:444',
            },
          },
          requestUrl: new URL(
            'https://editor.example.com:444/builder/preview/42'
          ),
        },
        fetch
      )
    ).toBe('<meta name="x">')
  })

  test('an unavailable HTML endpoint does not interrupt the page render', async () => {
    const fetch = vi.fn().mockRejectedValue(new Error('HTTP 404'))

    expect(await fetchBuilderHeadHtml(previewOptions, fetch)).toBe('')
  })
})
