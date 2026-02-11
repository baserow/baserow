import axios from 'axios'
import MockAdapter from 'axios-mock-adapter'
import httpMocks from 'node-mocks-http'

import createNuxt from '@baserow/test/helpers/create-nuxt'

let nuxt = null
let mock = null

// expire at 05/18/2033
const token =
  'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoxLCJ1c2VybmFtZSI6' +
  'InRlc3RAdGVzdCIsImV4cCI6MTk5OTk5OTk5OSwiZW1haWwiOiJ0ZXN0QHRlc3QubmwiL' +
  'CJpYXQiOjE1NjI3NzM0MTR9.8kNGEaddqqitRdL4iiwzoBSdMKdo92610dU7ReZxU1E'

// TODO MIG skipped
describe('index redirect', () => {
  beforeAll(async () => {
    mock = new MockAdapter(axios)

    // Because the token 'test1' exists it will be refreshed immediately, the
    // refresh endpoint is stubbed so that it will always provide a valid
    // unexpired token.
    mock.onPost('http://localhost/api/user/token-refresh/').reply(200, {
      access_token: token,
      user: {
        first_name: 'Test',
        username: 'test@test.nl',
      },
    })

    mock.onGet('http://localhost/api/auth-provider/login-options/').reply(200, {
      password: {
        type: 'password',
        enabled: true,
      },
    })

    nuxt = await createNuxt(true)
  }, 300000)

  afterAll(async () => {
    // Close the server to prevent open handles
    await nuxt.server.close()
  })

  test.skip('if not authenticated', async () => {
    const { redirected } = await nuxt.server.renderRoute('/')
    expect(redirected.path).toBe('/login')
    expect(redirected.status).toBe(302)
  })

  test.skip('if authenticated', async () => {
    const req = httpMocks.createRequest({
      headers: {
        host: `localhost`,
        cookie: `jwt_token=${token}`,
      },
      env: {
        PUBLIC_WEB_FRONTEND_URL: `https://localhost`,
      },
    })
    const res = httpMocks.createResponse()
    const { redirected } = await nuxt.server.renderRoute('/', { req, res })
    expect(redirected.path).toBe('/dashboard')
    expect(redirected.status).toBe(302)
  })

  test.skip('login page renders', async () => {
    const { html } = await nuxt.server.renderRoute('/login')
    expect(html).toContain('Login')
  })

  test.skip('sign up page renders', async () => {
    const { html } = await nuxt.server.renderRoute('/signup')
    expect(html).toContain('Sign up')
  })
})
