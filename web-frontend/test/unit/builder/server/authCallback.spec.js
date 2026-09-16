// @vitest-environment node
import { createApp, defineEventHandler, toWebHandler } from 'h3'
import callback from '../../../../modules/builder/server/middleware/authCallback'

vi.mock('nitropack/runtime', () => ({
  useRuntimeConfig: () => ({
    public: {
      publicWebFrontendUrl: 'https://baserow.example.com',
      builderPreviewUrl: 'http://preview.example.com',
      baserowFrontendCookiePrefix: 'test_',
    },
  }),
}))

const request = (path, origin = 'https://builder.example.com') => {
  const app = createApp()
  app.use(callback)
  app.use(defineEventHandler(() => 'page rendered'))
  return toWebHandler(app)(
    new Request(`${origin}${path}`, {
      headers: { host: new URL(origin).host },
    })
  )
}

describe('Builder SSO callback bridge', () => {
  test.each(['saml', 'oidc'])(
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

test.each(['saml', 'oidc'])(
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

test.each(['saml', 'oidc'])(
  'acknowledges %s preview attempts with a receipt usable on the preview host',
  async (provider) => {
    const response = await request(
      `/builder/preview/17/login?user_source_${provider}_token__42=token&user_source_login_attempt=${attemptId}`,
      'http://preview.example.com'
    )
    expect(response.headers.get('location')).toBe('/builder/preview/17/login')
    const receipt = response.headers
      .getSetCookie()
      .find((cookie) =>
        cookie.startsWith(`test_user_source_login_completed_${attemptId}=`)
      )
    expect(receipt).toContain('=1;')
    expect(receipt).toContain('Path=/;')
    expect(receipt).toContain('Max-Age=60')
    expect(receipt).toContain('SameSite=Lax')
    expect(receipt).not.toMatch(/Secure|Domain=/)
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
  expect(
    new URL(response.headers.get('location'), 'https://builder.example.com')
      .origin
  ).toBe('https://builder.example.com')
})

const attemptId = '00000000-0000-4000-8000-000000000001'

test('acknowledges the initiating SSO attempt only on a token callback', async () => {
  const response = await request(
    `/login?user_source_saml_token__42=token&user_source_login_attempt=${attemptId}`
  )
  expect(response.headers.get('location')).toBe('/login')
  expect(response.headers.get('set-cookie')).toContain(
    `test_user_source_login_completed_${attemptId}=1`
  )
  expect(response.headers.get('set-cookie')).toContain('Max-Age=60')
  const ordinary = await request(
    `/login?user_source_login_attempt=${attemptId}`
  )
  expect(ordinary.headers.get('set-cookie')).toBeNull()
})

test.each([
  '',
  'invalid',
  `${attemptId}&user_source_login_attempt=${attemptId}`,
])(
  'does not acknowledge a malformed or ambiguous attempt: %s',
  async (attempt) => {
    const response = await request(
      `/login?user_source_saml_token__42=token&user_source_login_attempt=${attempt}`
    )
    expect(response.headers.get('location')).toBe('/login')
    expect(response.headers.get('set-cookie')).not.toContain('login_completed')
  }
)
