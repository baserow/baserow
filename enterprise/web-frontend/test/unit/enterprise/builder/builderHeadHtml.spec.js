import { fetchBuilderHeadHtml } from '@baserow_enterprise/plugins/builderHeadHtml.server'
import { previewSharesEditorHostname } from '@baserow_enterprise/utils/builderHeadHtml'

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

describe('previewSharesEditorHostname', () => {
  test.each([
    ['http://localhost:3000', 'http://localhost:3000', true],
    ['http://localhost:3001', 'http://localhost:3000', true],
    ['https://preview.example.com', 'https://example.com', false],
    ['', 'https://example.com', true],
  ])('%s vs %s', (builderPreviewUrl, publicWebFrontendUrl, expected) => {
    expect(
      previewSharesEditorHostname({ builderPreviewUrl, publicWebFrontendUrl })
    ).toBe(expected)
  })
})
