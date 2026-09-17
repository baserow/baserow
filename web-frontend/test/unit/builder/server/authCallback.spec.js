// @vitest-environment node
import { createApp, defineEventHandler, toWebHandler } from 'h3'
import { $fetch } from 'ofetch'
import callback from '@baserow/modules/builder/server/middleware/authCallback'

vi.mock('ofetch', () => ({ $fetch: vi.fn() }))

beforeEach(() => {
  $fetch.mockReset()
  $fetch.mockResolvedValue({
    user_sources: [
      {
        id: 42,
        auth_providers: ['saml', 'oidc', 'custom_provider-v2'].map((type) => ({
          type,
          supports_callback: true,
        })),
      },
    ],
  })
})

vi.mock('nitropack/runtime', () => ({
  useRuntimeConfig: () => ({
    privateBackendUrl: 'http://backend:8000',
    public: {
      publicWebFrontendUrl: 'https://baserow.example.com',
      builderPreviewUrl: 'http://preview.example.com',
      baserowFrontendCookiePrefix: 'test_',
    },
  }),
}))

const request = (
  path,
  origin = 'https://builder.example.com',
  headers = {}
) => {
  const app = createApp()
  app.use(callback)
  app.use(defineEventHandler(() => 'page rendered'))
  return toWebHandler(app)(
    new Request(`${origin}${path}`, {
      headers: { host: new URL(origin).host, ...headers },
    })
  )
}

describe('Builder SSO callback bridge', () => {
  test.each(['saml', 'oidc', 'custom_provider-v2'])(
    'sets the existing host cookie and redirects before rendering for %s',
    async (provider) => {
      const response = await request(
        `/protected?tag=a&user_source_${provider}_token__42=test-refresh-token&tag=b&next=%252Fmembers`
      )
      expect(response.status).toBe(303)
      expect(response.headers.get('location')).toBe(
        '/protected?tag=a&tag=b&next=%252Fmembers'
      )
      const cookie = response.headers.get('set-cookie')
      expect(cookie).toContain('test_user_source_token=test-refresh-token')
      expect(cookie).toContain('Max-Age=604800')
      expect(cookie).toContain('Path=/')
      expect(cookie).toContain('SameSite=Lax')
      expect(cookie).toContain('Secure')
      expect(cookie).not.toMatch(/Domain=|HttpOnly/)
      expect(response.headers.get('cache-control')).toBe('no-store')
      expect(response.headers.get('referrer-policy')).toBe('no-referrer')
      expect(await response.text()).not.toContain('page rendered')
    }
  )
})

test.each(['saml', 'oidc', 'custom_provider-v2'])(
  'authenticates %s previews with the builder-scoped cookie',
  async (provider) => {
    for (const origin of [
      'http://preview.example.com',
      'https://baserow.example.com',
    ]) {
      const response = await request(
        `/builder/preview/17/members?user_source_${provider}_token__42=test-refresh-token`,
        origin
      )
      expect(response.status).toBe(303)
      expect(response.headers.get('location')).toBe(
        '/builder/preview/17/members'
      )
      const cookie = response.headers.get('set-cookie')
      expect(cookie).toContain(
        'test_baserow_builder_preview_user_source=test-refresh-token'
      )
      expect(cookie).toContain('Path=/builder/preview/17;')
      expect(cookie).toContain('SameSite=Lax')
      expect(cookie).not.toMatch(/Secure|Domain=/)
    }
  }
)

test('a published page with a preview-like path keeps the published cookie', async () => {
  const response = await request(
    '/builder/preview/17/members?user_source_saml_token__42=test-refresh-token'
  )
  const cookie = response.headers.get('set-cookie')
  expect(cookie).toContain('test_user_source_token=test-refresh-token')
  expect(cookie).toContain('Path=/;')
})

test.each([
  '/members?user_source_oidc_token__42=test-refresh-token',
  encodeURIComponent('/members?user_source_saml_token__99=test-refresh-token'),
  encodeURIComponent(
    '/members?user_source_custom_provider-v2_token__99=another-token'
  ),
  encodeURIComponent(encodeURIComponent('/members?secret=test-refresh-token')),
])('does not carry callback credentials inside next: %s', async (next) => {
  const response = await request(
    `/login?user_source_saml_token__42=test-refresh-token&next=${encodeURIComponent(next)}&lang=en`
  )
  expect(response.headers.get('location')).toBe('/login?lang=en')
  expect(await response.text()).not.toContain('test-refresh-token')
})

test.each([
  '?user_source_saml_token__42=',
  '?user_source_saml_token__42=one&user_source_saml_token__42=two',
  '?user_source_saml_token__42=one&user_source_oidc_token__99=two',
])(
  'cleans empty or ambiguous callbacks without setting credentials: %s',
  async (query) => {
    const response = await request(`/login${query}`)
    expect(response.status).toBe(303)
    expect(response.headers.get('location')).toBe('/login')
    expect(response.headers.get('set-cookie')).toBeNull()
  }
)

test('ordinary requests reach the renderer without a redirect or cookie', async () => {
  const response = await request('/members?next=%252Fhome&lang=en')
  expect(response.status).toBe(200)
  expect(response.headers.get('set-cookie')).toBeNull()
  expect(await response.text()).toBe('page rendered')
})

test('preserves an encoded next destination containing a literal percent', async () => {
  const response = await request(
    '/login?user_source_saml_token__42=test-refresh-token&next=%252Fsearch%253Fdiscount%253D10%252525'
  )
  expect(response.headers.get('location')).toBe(
    '/login?next=%252Fsearch%253Fdiscount%253D10%252525'
  )
})

test('keeps a double-slash request path on the current host', async () => {
  const response = await request(
    '//other.example.com/page?user_source_saml_token__42=test-refresh-token'
  )
  expect(response.headers.get('location')).toMatch(/^\/(?![/\\])/)
  expect(
    new URL(response.headers.get('location'), 'https://builder.example.com')
      .origin
  ).toBe('https://builder.example.com')
})

test.each([
  { user_sources: [{ id: 42, auth_providers: [{ type: 'password' }] }] },
  { user_sources: [{ id: 99, auth_providers: [{ type: 'saml' }] }] },
  { user_sources: [] },
  {
    user_sources: [
      { id: 42, auth_providers: [{ type: 'saml', supports_callback: false }] },
    ],
  },
])(
  'does not replace the session for an unconfigured callback',
  async (builder) => {
    $fetch.mockResolvedValue(builder)
    const response = await request(
      '/login?user_source_saml_token__42=attacker-token'
    )
    expect(response.status).toBe(303)
    expect(response.headers.get('set-cookie')).toBeNull()
    expect(response.headers.get('location')).toBe('/login')
  }
)
test('does not install a token when the Builder cannot be loaded', async () => {
  $fetch.mockRejectedValue({ statusCode: 404 })
  const response = await request(
    '/login?user_source_saml_token__42=attacker-token'
  )
  expect(response.headers.get('set-cookie')).toBeNull()
})

test('resolves published callbacks by domain without forwarding browser cookies', async () => {
  await request('/login?user_source_saml_token__42=token', undefined, {
    cookie: 'unrelated=secret',
  })
  expect($fetch).toHaveBeenCalledWith(
    'builder/domains/published/by_name/builder.example.com/',
    {
      baseURL: 'http://backend:8000/api/',
      headers: {},
      retry: 0,
    }
  )
})
test('resolves previews using only the preview SSR credential', async () => {
  await request(
    '/builder/preview/17/login?user_source_saml_token__42=token',
    'http://preview.example.com',
    {
      cookie:
        'test_baserow_builder_preview_ssr=preview-session; unrelated=secret',
    }
  )
  expect($fetch).toHaveBeenCalledWith('builder/preview/17/current/', {
    baseURL: 'http://backend:8000/api/',
    headers: { Cookie: 'test_baserow_builder_preview=preview-session' },
    retry: 0,
  })
})
test('resolves the published-by-ID route on the frontend host', async () => {
  await request(
    '/builder/published/17/login?user_source_saml_token__42=token',
    'https://baserow.example.com'
  )
  expect($fetch.mock.calls[0][0]).toBe('builder/domains/published/by_id/17/')
})
test.each([401, 403, 404])(
  'rejects unauthorized preview callbacks (%s)',
  async (statusCode) => {
    $fetch.mockRejectedValue({ statusCode })
    const response = await request(
      '/builder/preview/17/login?user_source_saml_token__42=token',
      'http://preview.example.com'
    )
    expect(response.headers.get('set-cookie')).toBeNull()
    expect(response.status).toBe(303)
  }
)

test('a password provider cannot be used as a callback even when configured', async () => {
  $fetch.mockResolvedValue({
    user_sources: [
      {
        id: 42,
        auth_providers: [
          { type: 'local_baserow_password', supports_callback: false },
        ],
      },
    ],
  })
  const response = await request(
    '/login?user_source_local_baserow_password_token__42=attacker-token'
  )
  expect(response.headers.get('set-cookie')).toBeNull()
  expect(response.status).toBe(303)
})
