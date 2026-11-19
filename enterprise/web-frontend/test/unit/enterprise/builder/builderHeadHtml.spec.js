import { fetchBuilderHeadHtml } from '@baserow_enterprise/plugins/builderHeadHtml.server'

describe('Fetching Custom Code HTML during a Builder render', () => {
  const builder = { id: 42, custom_code: { has_html: true } }
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
    previewSsrCookieHeader: 'test_baserow_builder_preview=signed-session',
    requestUrl: new URL('https://preview.example.com/builder/preview/42'),
  }

  test('fetches the published fragment verbatim and omits preview credentials', async () => {
    const html = '\n<meta name="description" content="Baserow">\n'
    const fetch = vi.fn().mockResolvedValue({ html })

    expect(
      await fetchBuilderHeadHtml({ ...previewOptions, mode: 'public' }, fetch)
    ).toBe(html)
    expect(fetch).toHaveBeenCalledWith(
      'custom_code/42/html/public/',
      expect.objectContaining({
        baseURL: 'http://backend:8000/api/',
        headers: { Accept: 'application/json' },
      })
    )
  })

  test('uses the scoped SSR Preview session for the isolated preview host', async () => {
    const fetch = vi.fn().mockResolvedValue({ html: '<style></style>' })

    expect(await fetchBuilderHeadHtml(previewOptions, fetch)).toBe(
      '<style></style>'
    )
    expect(fetch).toHaveBeenCalledWith(
      'builder/preview/42/custom-code/html/',
      expect.objectContaining({
        headers: {
          Accept: 'application/json',
          Cookie: 'test_baserow_builder_preview=signed-session',
        },
      })
    )
  })

  test.each([
    ['untrusted content', { builder: { ...builder, untrusted_content: true } }],
    [
      'empty content',
      { builder: { id: 42, custom_code: { has_html: false } } },
    ],
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
      },
    ],
  ])('skips requests for %s', async (_, overrides) => {
    const fetch = vi.fn()

    expect(
      await fetchBuilderHeadHtml({ ...previewOptions, ...overrides }, fetch)
    ).toBe('')
    expect(fetch).not.toHaveBeenCalled()
  })

  test('an unavailable HTML endpoint does not interrupt the page render', async () => {
    const fetch = vi.fn().mockRejectedValue(new Error('HTTP 404'))

    expect(await fetchBuilderHeadHtml(previewOptions, fetch)).toBe('')
  })
})
