import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { defineComponent } from 'vue'

import { usePublicAgentChat } from '@baserow_enterprise/composables/usePublicAgentChat'
import PublicAgentChatPage from '@baserow_enterprise/pages/publicAgentChat'

const mocks = vi.hoisted(() => ({ service: {} }))

vi.mock('@baserow_enterprise/services/publicAgentChat', () => ({
  default: () => mocks.service,
}))

const SLUG = 'support'
const STORAGE_KEY = `baserow-agent-public-chat:${SLUG}`
const OPEN = {
  title: 'Support',
  welcome_text: 'Hi',
  password_protected: false,
  has_access: true,
}
const PROTECTED = {
  title: '',
  welcome_text: '',
  password_protected: true,
  has_access: false,
}

const visitor = { id: 'm1', role: 'visitor', content: 'Hello', status: null }
const reply = (status, content = '') => ({
  id: 'm2',
  role: 'assistant',
  content,
  status,
})
const refused = (status, error) =>
  Object.assign(new Error(), { response: { status, data: { error } } })

let streams

async function mountChat(info = OPEN) {
  let chat
  const wrapper = await mountSuspended(
    defineComponent({
      setup() {
        chat = usePublicAgentChat(SLUG, info)
        return () => null
      },
    })
  )
  await flushPromises()
  return { chat, wrapper }
}

const storedTokens = () => JSON.parse(localStorage.getItem(STORAGE_KEY))
const contents = (chat) => chat.messages.value.map(({ content }) => content)

describe('usePublicAgentChat', () => {
  beforeEach(() => {
    streams = []
    mocks.service = {
      getInfo: vi.fn().mockResolvedValue({ data: OPEN }),
      authorize: vi.fn(),
      startConversation: vi.fn().mockResolvedValue({
        data: {
          token: 'conversation',
          messages: [visitor, reply('queued')],
          run_id: 'run',
        },
      }),
      getConversation: vi.fn(),
      sendMessage: vi.fn(),
      stop: vi.fn(),
      stream: vi.fn(
        (slug, runId, cursor, token, onRecord) =>
          new Promise((resolve, reject) =>
            streams.push({ cursor, token, onRecord, resolve, reject })
          )
      ),
    }
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
    localStorage.clear()
  })

  test('an open chat with nothing stored is ready and shows no messages', async () => {
    const { chat } = await mountChat()

    expect(chat.needsPassword.value).toBe(false)
    expect(chat.messages.value).toEqual([])
    expect(mocks.service.getConversation).not.toHaveBeenCalled()
  })

  test('a protected chat asks for the password until its info loads with the right one', async () => {
    const { chat } = await mountChat(PROTECTED)
    expect(chat.needsPassword.value).toBe(true)

    mocks.service.authorize.mockRejectedValueOnce(refused(401))
    await chat.authorize('wrong')
    expect(chat.passwordError.value).toBe(true)
    expect(chat.needsPassword.value).toBe(true)

    mocks.service.authorize.mockResolvedValue({
      data: { access_token: 'access' },
    })
    mocks.service.getInfo.mockRejectedValueOnce(refused(502))
    await expect(chat.authorize('right')).rejects.toThrow()
    expect(chat.needsPassword.value).toBe(true)

    mocks.service.getInfo.mockResolvedValueOnce({
      data: { ...OPEN, password_protected: true },
    })
    await chat.authorize('right')

    expect(chat.passwordError.value).toBe(false)
    expect(chat.needsPassword.value).toBe(false)
    expect(chat.info.value.title).toBe('Support')
    expect(mocks.service.getInfo).toHaveBeenCalledWith(SLUG, 'access')
    expect(storedTokens().accessToken).toBe('access')
  })

  test('a stored token opens a protected chat only once its info loads with it', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ accessToken: 'access' }))
    mocks.service.getInfo.mockRejectedValueOnce(refused(502))
    const { chat: failed } = await mountChat(PROTECTED)
    expect(failed.needsPassword.value).toBe(true)

    mocks.service.getInfo.mockResolvedValueOnce({
      data: { ...OPEN, password_protected: true },
    })
    const { chat } = await mountChat(PROTECTED)
    expect(mocks.service.getInfo).toHaveBeenLastCalledWith(SLUG, 'access')
    expect(chat.needsPassword.value).toBe(false)
  })

  test('send shows the message, then the streamed reply, then the saved reply', async () => {
    const { chat } = await mountChat()

    await chat.send('Hello')

    expect(storedTokens().conversationToken).toBe('conversation')
    expect(contents(chat)).toEqual(['Hello', ''])
    expect(chat.replying.value).toBe(true)
    const [stream] = streams
    expect(stream.token).toBe('conversation')

    stream.onRecord({
      kind: 'text.delta',
      data: { segment: 0, text: 'Hi' },
      cursor: 'g:1-0',
    })
    stream.onRecord({
      kind: 'text.delta',
      data: { segment: 0, text: ' there' },
      cursor: 'g:2-0',
    })
    expect(contents(chat)).toEqual(['Hello', 'Hi there'])

    stream.onRecord({
      kind: 'run.finished',
      data: { status: 'completed', message: reply('completed', 'Hi there!') },
      cursor: 'g:2-0',
    })
    expect(contents(chat)).toEqual(['Hello', 'Hi there!'])
    expect(chat.replying.value).toBe(false)
  })

  test('a send whose request failed is sent again with the same ids, and a new message gets new ones', async () => {
    mocks.service.startConversation.mockRejectedValueOnce(
      new Error('Network error occurred')
    )
    mocks.service.sendMessage.mockResolvedValue({
      data: { messages: [], run_id: null },
    })
    const { chat } = await mountChat()

    expect(await chat.send('Hello')).toBe(false)
    expect(await chat.send('Hello')).toBe(true)
    await chat.send('Hello')

    const [[, first], [, retry]] = mocks.service.startConversation.mock.calls
    expect(first).toEqual({
      key: expect.stringMatching(/^[0-9a-f-]{32,128}$/),
      content: 'Hello',
    })
    expect(retry).toEqual(first)
    const [[, next]] = mocks.service.sendMessage.mock.calls
    expect(next).toEqual({ uuid: expect.any(String), content: 'Hello' })
    expect(next.uuid).not.toBe(first.key)
  })

  test('an accepted send a history reload already shows is not shown twice', async () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ conversationToken: 'conversation' })
    )
    const again = { id: 'm3', role: 'visitor', content: 'Again', status: null }
    const answer = { ...reply('completed', 'Sure'), id: 'm4' }
    const earlier = [visitor, reply('completed', 'Hi!')]
    mocks.service.getConversation
      .mockResolvedValueOnce({ data: { messages: earlier, run_id: null } })
      .mockResolvedValue({
        data: { messages: [...earlier, again, answer], run_id: null },
      })
    let accept
    mocks.service.sendMessage.mockReturnValue(
      new Promise((resolve) => (accept = resolve))
    )
    const { chat } = await mountChat()

    const sent = chat.send('Again')
    await chat.sync()
    accept({ data: { messages: [again, answer], run_id: null } })
    await sent

    expect(contents(chat)).toEqual(['Hello', 'Hi!', 'Again', 'Sure'])
  })

  test('a conversation refused because the chat got a password asks for it', async () => {
    const { chat } = await mountChat()
    await chat.send('Hello')
    mocks.service.sendMessage.mockRejectedValueOnce(refused(401))
    mocks.service.getInfo.mockResolvedValueOnce({ data: PROTECTED })

    expect(await chat.send('Again')).toBe(false)

    expect(mocks.service.getInfo).toHaveBeenCalledWith(SLUG, null)
    expect(chat.needsPassword.value).toBe(true)
    expect(storedTokens().conversationToken).toBeFalsy()
  })

  test('a stored conversation whose first load fails says so until it loads', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ conversationToken: 'conversation' })
    )
    mocks.service.getConversation
      .mockRejectedValueOnce(refused(502))
      .mockResolvedValue({
        data: { messages: [visitor, reply('completed', 'Hi!')], run_id: null },
      })
    const { chat } = await mountChat()
    expect(chat.messages.value).toEqual([])
    expect(chat.restoreFailed.value).toBe(true)

    await vi.advanceTimersByTimeAsync(2000)

    expect(contents(chat)).toEqual(['Hello', 'Hi!'])
    expect(chat.restoreFailed.value).toBe(false)
  })

  test('the page shows a failing first load above a composer that stays usable', async () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ conversationToken: 'conversation' })
    )
    mocks.service.getConversation.mockRejectedValue(refused(502))
    const wrapper = await mountSuspended(PublicAgentChatPage, {
      route: `/public/agent-chat/${SLUG}`,
    })
    await flushPromises()

    expect(wrapper.find('.public-agent-chat__restore-failed').text()).toBe(
      'publicAgentChat.restoreFailed'
    )
    expect(
      wrapper.find('.public-agent-chat__composer textarea').attributes()
    ).not.toHaveProperty('disabled')
    wrapper.unmount()
  })

  test('the page shows a stopped reply without text as stopped', async () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ conversationToken: 'conversation' })
    )
    mocks.service.getConversation.mockResolvedValue({
      data: { messages: [visitor, reply('cancelled')], run_id: null },
    })
    const wrapper = await mountSuspended(PublicAgentChatPage, {
      route: `/public/agent-chat/${SLUG}`,
    })
    await flushPromises()

    expect(
      wrapper.findAll('.chat-message__bubble').map((bubble) => bubble.text())
    ).toEqual(['Hello', 'publicAgentChat.stopped'])
    wrapper.unmount()
  })

  test('a stored conversation is restored and followed; a refused one is forgotten', async () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ conversationToken: 'conversation' })
    )
    mocks.service.getConversation.mockResolvedValueOnce({
      data: { messages: [visitor, reply('running')], run_id: 'run' },
    })
    const { chat } = await mountChat()

    expect(mocks.service.getConversation).toHaveBeenCalledWith(
      SLUG,
      'conversation'
    )
    expect(contents(chat)).toEqual(['Hello', ''])
    expect(chat.replying.value).toBe(true)
    expect(streams).toHaveLength(1)

    mocks.service.getConversation.mockRejectedValueOnce(refused(401))
    const { chat: refusedChat } = await mountChat()

    expect(storedTokens().conversationToken).toBeFalsy()
    expect(refusedChat.messages.value).toEqual([])
    expect(refusedChat.needsPassword.value).toBe(false)
  })

  test('a waiting reply disables sending and syncs until its status changes', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ conversationToken: 'conversation' })
    )
    mocks.service.getConversation
      .mockResolvedValueOnce({
        data: { messages: [visitor, reply('waiting')], run_id: null },
      })
      .mockResolvedValueOnce({
        data: { messages: [visitor, reply('waiting')], run_id: null },
      })
      .mockResolvedValue({
        data: { messages: [visitor, reply('running')], run_id: 'run' },
      })
    const { chat } = await mountChat()
    expect(chat.waiting.value).toBe(true)

    await vi.advanceTimersByTimeAsync(5000)
    expect(chat.waiting.value).toBe(true)
    await vi.advanceTimersByTimeAsync(5000)

    expect(chat.waiting.value).toBe(false)
    expect(streams).toHaveLength(1)
    await vi.advanceTimersByTimeAsync(10000)
    expect(mocks.service.getConversation).toHaveBeenCalledTimes(3)
  })

  test('a failed stream syncs and follows again while the reply still runs', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    mocks.service.getConversation.mockResolvedValue({
      data: { messages: [visitor, reply('running')], run_id: 'run' },
    })
    const { chat } = await mountChat()
    await chat.send('Hello')
    streams[0].onRecord({
      kind: 'text.delta',
      data: { segment: 0, text: 'Hi' },
      cursor: 'g:1-0',
    })

    streams[0].reject(new Error('Network error occurred'))
    await vi.advanceTimersByTimeAsync(2000)

    expect(mocks.service.getConversation).toHaveBeenCalledTimes(1)
    expect(streams).toHaveLength(2)
    expect(streams[1].cursor).toBe('g:1-0')
    expect(contents(chat)).toEqual(['Hello', 'Hi'])
  })

  test('a failed sync while the reply still runs is tried again until the reply finishes', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    mocks.service.getConversation
      .mockRejectedValueOnce(new Error('Network error occurred'))
      .mockResolvedValue({
        data: { messages: [visitor, reply('completed', 'Hi!')], run_id: null },
      })
    const { chat } = await mountChat()
    await chat.send('Hello')

    streams[0].reject(new Error('Network error occurred'))
    await vi.advanceTimersByTimeAsync(4000)

    expect(mocks.service.getConversation).toHaveBeenCalledTimes(2)
    expect(contents(chat)).toEqual(['Hello', 'Hi!'])
    expect(chat.replying.value).toBe(false)
  })

  test('a failed poll of a waiting reply does not end the polling', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ conversationToken: 'conversation' })
    )
    mocks.service.getConversation
      .mockResolvedValueOnce({
        data: { messages: [visitor, reply('waiting')], run_id: null },
      })
      .mockRejectedValueOnce(refused(502))
      .mockResolvedValue({
        data: { messages: [visitor, reply('completed', 'Done')], run_id: null },
      })
    const { chat } = await mountChat()

    await vi.advanceTimersByTimeAsync(5000)
    expect(chat.waiting.value).toBe(true)
    await vi.advanceTimersByTimeAsync(2000)

    expect(chat.waiting.value).toBe(false)
  })

  test('a stream silent for the idle time is reopened through a sync', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    mocks.service.getConversation.mockResolvedValue({
      data: { messages: [visitor, reply('running')], run_id: 'run' },
    })
    const { chat } = await mountChat()
    await chat.send('Hello')

    await vi.advanceTimersByTimeAsync(10000)
    streams[0].onRecord({ kind: 'run.heartbeat', data: {}, cursor: 'g:1-0' })
    await vi.advanceTimersByTimeAsync(10000)
    expect(mocks.service.getConversation).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(7000)
    expect(mocks.service.getConversation).toHaveBeenCalledTimes(1)
    expect(streams).toHaveLength(2)
    expect(streams[1].cursor).toBe('g:1-0')
  })

  test('a chat that is gone is unavailable and keeps the messages', async () => {
    const { chat } = await mountChat()
    await chat.send('Hello')
    mocks.service.sendMessage.mockRejectedValueOnce(
      refused(404, 'ERROR_AGENT_CHANNEL_DOES_NOT_EXIST')
    )

    await chat.send('Again')

    expect(chat.unavailable.value).toBe(true)
    expect(contents(chat)).toEqual(['Hello', ''])
    expect(storedTokens().conversationToken).toBe('conversation')
  })

  test('reset forgets the conversation, and storage that throws never breaks the page', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ accessToken: 'access' }))
    const { chat } = await mountChat()
    await chat.send('Hello')

    chat.reset()

    expect(chat.messages.value).toEqual([])
    expect(storedTokens()).toEqual({
      accessToken: 'access',
      conversationToken: null,
    })

    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    const { chat: blockedChat } = await mountChat()
    await blockedChat.send('Hello')

    expect(contents(blockedChat)).toEqual(['Hello', ''])
  })
})
