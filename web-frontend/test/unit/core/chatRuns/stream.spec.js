import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import chatRunsService from '@baserow/modules/core/services/chatRuns'

const RECORDS = [
  {
    kind: 'text.delta',
    data: { segment: 0, text: 'first\n\nsecond' },
    cursor: 'a:1-0',
  },
  {
    kind: 'text.delta',
    data: { segment: 0, text: 'Ünïcödé 😀' },
    cursor: 'a:2-0',
  },
]
const BODY =
  '\n\n' + RECORDS.map((record) => JSON.stringify(record) + '\n\n').join('')
// Its middle paragraph parses as JSON, like a record would.
const ERROR_PAGE = '<h1>Bad gateway</h1>\n\n502\n\n<p>Try again later.</p>'

class FakeXHR {
  constructor() {
    this.responseText = ''
    this.status = 200
    this.statusText = 'OK'
    this.headers = {}
    FakeXHR.last = this
  }

  open(method, url) {
    this.method = method
    this.url = url
  }

  setRequestHeader(key, value) {
    this.headers[key] = value
  }

  send() {}

  abort() {
    this.aborted = true
    this.onabort()
  }

  receive(text) {
    this.responseText += text
    this.onprogress()
  }

  complete(status = 200, text = '') {
    this.status = status
    this.responseText += text
    this.onprogress()
    this.onload()
  }
}

const client = {
  get: vi.fn((url, config) =>
    config.adapter({
      baseURL: 'http://localhost:8000/api',
      url,
      params: config.params,
      method: 'get',
      headers: { Authorization: 'JWT token' },
    })
  ),
}

const stream = (onRecord, signal) =>
  chatRunsService(client).stream('run-id', 'a:0-5', onRecord, signal)

describe('core chat run stream', () => {
  beforeEach(() => vi.stubGlobal('XMLHttpRequest', FakeXHR))
  afterEach(() => vi.unstubAllGlobals())

  test('reads the run after the cursor and hands over each record once', async () => {
    for (let split = 0; split <= BODY.length; split++) {
      const received = []
      const request = stream((record) => received.push(record))
      FakeXHR.last.receive(BODY.substring(0, split))
      FakeXHR.last.receive(BODY.substring(split))
      FakeXHR.last.complete()
      await request
      expect({ split, received }).toEqual({ split, received: RECORDS })
    }
    expect(FakeXHR.last.method).toBe('GET')
    expect(FakeXHR.last.url).toBe(
      'http://localhost:8000/api/chat-runs/run-id/stream/?cursor=a:0-5'
    )
    expect(FakeXHR.last.headers.Authorization).toBe('JWT token')
  })

  test.each([
    [
      'a JSON error',
      404,
      JSON.stringify({ error: 'ERROR_CHAT_RUN_DOES_NOT_EXIST' }),
      { error: 'ERROR_CHAT_RUN_DOES_NOT_EXIST' },
    ],
    ['null', 500, 'null', { error: 'REQUEST_FAILED', detail: 'null' }],
    [
      'an HTML page',
      502,
      ERROR_PAGE,
      { error: 'REQUEST_FAILED', detail: ERROR_PAGE },
    ],
  ])(
    'rejects a failed response with %s as its body',
    async (_, status, body, data) => {
      const onRecord = vi.fn()
      const request = stream(onRecord)
      FakeXHR.last.complete(status, body)
      await expect(request).rejects.toMatchObject({
        config: expect.objectContaining({ url: expect.any(String) }),
        response: { status, data },
      })
      expect(onRecord).not.toHaveBeenCalled()
    }
  )

  test('aborting closes the response', async () => {
    const controller = new AbortController()
    const request = stream(() => {}, controller.signal)
    controller.abort()
    await expect(request).rejects.toMatchObject({ cancelled: true })
    expect(FakeXHR.last.aborted).toBe(true)
  })

  test('an expired token is refreshed once and the stream is read again', async () => {
    const testApp = new TestApp()
    try {
      const jwt = (iat) => `e30.${btoa(JSON.stringify({ user_id: 1, iat }))}.`
      const [expired, refreshed, user] = [jwt(1), jwt(2), { id: 1 }]
      const auth = { user, access_token: expired, refresh_token: expired }
      testApp.store.dispatch('auth/forceSetUserData', auth)
      testApp.mock
        .onPost('/user/token-refresh/')
        .reply(200, { user, access_token: refreshed })
      const received = []
      const { $client } = testApp.getApp()
      const request = chatRunsService($client).stream(
        'run-id',
        null,
        (record) => received.push(record)
      )
      await flushPromises()
      const refused = FakeXHR.last
      refused.complete(401, '{"error": "ERROR_INVALID_ACCESS_TOKEN"}')
      await flushPromises()
      expect(FakeXHR.last).not.toBe(refused)
      expect(FakeXHR.last.headers.Authorization).toBe(`JWT ${refreshed}`)
      FakeXHR.last.receive(BODY)
      FakeXHR.last.complete()
      await request
      expect(received).toEqual(RECORDS)
      expect(testApp.mock.history.post).toHaveLength(1)
    } finally {
      await testApp.afterEach()
    }
  })
})
