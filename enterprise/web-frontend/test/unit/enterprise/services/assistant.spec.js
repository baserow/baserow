import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import AssistantService from '@baserow_enterprise/services/assistant'

const CHAT_UUID = '11111111-1111-1111-1111-111111111111'

const EVENTS = [
  { type: 'ai_started', message_id: 7 },
  { type: 'thinking', content: 'Looking at your table' },
  // Embedded newlines prove the delimiter survives json.dumps escaping.
  { type: 'reasoning', id: 'r1', content: 'first\n\nsecond' },
  { type: 'message', id: 'm1', content: 'Ünïcödé 😀 answer', sources: [] },
]

const BODY = EVENTS.map((event) => JSON.stringify(event) + '\n\n').join('')

class FakeXHR {
  constructor() {
    this.responseText = ''
    this.status = 200
    this.statusText = 'OK'
    this.aborted = false
    FakeXHR.instances.push(this)
  }

  open() {}

  setRequestHeader() {}

  send() {}

  abort() {
    this.aborted = true
    this.onabort()
  }

  receive(text) {
    this.responseText += text
    this.onprogress()
  }

  complete(status = 200) {
    this.status = status
    this.onload()
  }
}

FakeXHR.instances = []

const makeClient = () => ({
  defaults: { baseURL: 'http://localhost:8000/api' },
  post: vi.fn((url, data, config) =>
    config.adapter({
      baseURL: config.baseURL,
      url,
      headers: { 'Content-Type': 'application/json' },
      data: JSON.stringify(data),
    })
  ),
})

/**
 * Streams `body` through the adapter using the given chunk boundaries and
 * returns every record the consumer received.
 */
const streamBody = async (body, boundaries, { complete = true } = {}) => {
  const received = []
  const request = AssistantService(makeClient()).sendMessage(
    CHAT_UUID,
    'hello',
    {},
    (update) => {
      received.push(update)
    }
  )
  const xhr = FakeXHR.instances[FakeXHR.instances.length - 1]

  let offset = 0
  for (const boundary of [...boundaries, body.length]) {
    if (boundary > offset) {
      xhr.receive(body.substring(offset, boundary))
      offset = boundary
    }
  }
  if (complete) {
    xhr.complete()
    await request
  }
  return { received, request, xhr }
}

describe('assistant service streaming adapter', () => {
  beforeEach(() => {
    FakeXHR.instances = []
    vi.stubGlobal('XMLHttpRequest', FakeXHR)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  test('delivers every record exactly once for every possible split', async () => {
    for (let split = 0; split <= BODY.length; split++) {
      const { received } = await streamBody(BODY, [split])
      expect({ split, received }).toEqual({ split, received: EVENTS })
    }
  })

  test('delivers every record exactly once for every three-way split', async () => {
    for (let first = 0; first <= BODY.length; first += 7) {
      for (let second = first; second <= BODY.length; second += 11) {
        const { received } = await streamBody(BODY, [first, second])
        expect({ first, second, received }).toEqual({
          first,
          second,
          received: EVENTS,
        })
      }
    }
  })

  test('delivers every record when a chunk ends inside the delimiter', async () => {
    const delimiterOffsets = []
    for (let i = 0; i < BODY.length - 1; i++) {
      if (BODY.substring(i, i + 2) === '\n\n') {
        delimiterOffsets.push(i, i + 1, i + 2)
      }
    }
    expect(delimiterOffsets.length).toBe(EVENTS.length * 3)

    for (const offset of delimiterOffsets) {
      const { received } = await streamBody(BODY, [offset])
      expect({ offset, received }).toEqual({ offset, received: EVENTS })
    }
  })

  // responseText never exposes a partial multi-byte sequence, so this is the worst case.
  test('delivers a record whose astral character is split across chunks', async () => {
    const emojiIndex = BODY.indexOf('😀')
    expect(BODY.charCodeAt(emojiIndex)).toBeGreaterThanOrEqual(0xd800)

    const { received } = await streamBody(BODY, [emojiIndex + 1])
    expect(received).toEqual(EVENTS)
  })

  test('delivers several complete records from a single progress event', async () => {
    const { received } = await streamBody(BODY, [])
    expect(received).toEqual(EVENTS)
  })

  test('does not redeliver records when a progress event adds no bytes', async () => {
    const received = []
    const request = AssistantService(makeClient()).sendMessage(
      CHAT_UUID,
      'hello',
      {},
      (update) => received.push(update)
    )
    const xhr = FakeXHR.instances[0]

    xhr.receive(BODY)
    xhr.onprogress()
    xhr.onprogress()
    xhr.complete()
    await request

    expect(received).toEqual(EVENTS)
  })

  test('flushes a final record that never received its delimiter', async () => {
    const truncated = BODY.slice(0, -'\n\n'.length)
    const { received } = await streamBody(truncated, [truncated.length - 5])

    expect(received).toEqual(EVENTS)
  })

  test('reports a truncated tail instead of delivering it', async () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => {})
    const truncated = BODY + '{"type": "message", "content": "cut'
    const { received } = await streamBody(truncated, [BODY.length])

    expect(received).toEqual(EVENTS)
    expect(error).toHaveBeenCalledTimes(1)
    expect(error.mock.calls[0][0]).toContain('unparsable record')
  })

  test('skips a corrupt record but keeps delivering the rest', async () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => {})
    const corrupt =
      JSON.stringify(EVENTS[0]) +
      '\n\nNone' +
      JSON.stringify(EVENTS[1]) +
      '\n\n' +
      JSON.stringify(EVENTS[2]) +
      '\n\n'
    const { received } = await streamBody(corrupt, [])

    expect(received).toEqual([EVENTS[0], EVENTS[2]])
    expect(error).toHaveBeenCalledTimes(1)
    expect(error.mock.calls[0][0]).toContain('unparsable record')
  })

  test('keeps record order when the consumer is asynchronous', async () => {
    const received = []
    const request = AssistantService(makeClient()).sendMessage(
      CHAT_UUID,
      'hello',
      {},
      async (update) => {
        await new Promise((resolve) => setTimeout(resolve, 0))
        received.push(update)
      }
    )
    const xhr = FakeXHR.instances[0]

    for (const event of EVENTS) {
      xhr.receive(JSON.stringify(event) + '\n\n')
    }
    xhr.complete()
    await request

    expect(received).toEqual(EVENTS)
  })

  test('resolves only after every record has been handled', async () => {
    const received = []
    const request = AssistantService(makeClient()).sendMessage(
      CHAT_UUID,
      'hello',
      {},
      async (update) => {
        await new Promise((resolve) => setTimeout(resolve, 0))
        received.push(update)
      }
    )
    const xhr = FakeXHR.instances[0]

    xhr.receive(BODY)
    xhr.complete()
    await request

    expect(received).toEqual(EVENTS)
  })

  test('a throwing consumer does not stop the remaining records', async () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => {})
    const received = []
    const request = AssistantService(makeClient()).sendMessage(
      CHAT_UUID,
      'hello',
      {},
      (update) => {
        if (update.type === 'thinking') {
          throw new Error('consumer exploded')
        }
        received.push(update)
      }
    )
    const xhr = FakeXHR.instances[0]

    xhr.receive(BODY)
    xhr.complete()
    await request

    expect(received).toEqual([EVENTS[0], EVENTS[2], EVENTS[3]])
    expect(error.mock.calls[0][0]).toContain('record handler failed')
  })

  test('rejects without delivering records on a non 2xx response', async () => {
    const received = []
    const request = AssistantService(makeClient()).sendMessage(
      CHAT_UUID,
      'hello',
      {},
      (update) => received.push(update)
    )
    const xhr = FakeXHR.instances[0]

    xhr.responseText = JSON.stringify({ detail: 'nope', error: 'ERROR_X' })
    xhr.complete(400)

    await expect(request).rejects.toMatchObject({
      response: { status: 400, data: { error: 'ERROR_X' } },
    })
    expect(received).toEqual([])
  })
})
