import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import assistantService from '@baserow_enterprise/services/assistant'
import coreService from '@baserow/modules/core/services/chatRuns'
import AssistantPanel from '@baserow_enterprise/components/assistant/AssistantPanel'
import {
  createRunsTestApp,
  destroyRunsTestApp,
  cursor,
  runRecord,
  applySnapshot,
} from './assistantRunHelpers'

vi.mock('@baserow_enterprise/services/assistant', () => ({ default: vi.fn() }))
vi.mock('@baserow/modules/core/services/chatRuns', () => ({ default: vi.fn() }))

const workspace = { id: 1, name: 'Test workspace' }
const uuid = '22222222-2222-4222-8222-222222222222'
const human = { id: 501, type: 'human', content: 'Build a tracker' }

describe('Kuma panel with a store-owned HTTP follower', () => {
  let testApp, store, wrapper, receive, api
  beforeEach(async () => {
    testApp = createRunsTestApp()
    store = testApp.store
    api = {
      stream: vi.fn((run, after, onRecord) => {
        receive = onRecord
        return new Promise(() => {})
      }),
      get: vi.fn().mockResolvedValue({ status: 'running' }),
      cancel: vi.fn().mockResolvedValue({ status: 'running' }),
    }
    coreService.mockReturnValue(api)
    assistantService.mockReturnValue({
      fetchChats: vi.fn().mockResolvedValue({ results: [] }),
      fetchChatMessages: vi.fn().mockResolvedValue({
        chat_id: 7,
        messages: [human],
        active_run: { id: 'run-1', status: 'running' },
      }),
    })
    await store.dispatch('workspace/forceCreate', workspace)
    wrapper = await testApp.mount(AssistantPanel, { props: { workspace } })
    store.commit('assistant/SET_CHATS', [
      { uuid, chat_id: 7, title: 'Tracker' },
    ])
    await store.dispatch(
      'assistant/selectChat',
      store.getters['assistant/chats'][0]
    )
    await flushPromises()
  })
  afterEach(() => destroyRunsTestApp(testApp))
  const status = () => wrapper.find('.assistant__status-message').text()

  test('shows streamed output, tool progress, then that Kuma is answering', async () => {
    await receive(
      runRecord(
        'ai/reasoning',
        { content: 'Looking at your tables' },
        { cursor: cursor(1) }
      )
    )
    await receive(
      runRecord(
        'ai/thinking',
        { content: 'Creating rows' },
        { cursor: cursor(2) }
      )
    )
    expect(wrapper.text()).toContain('Looking at your tables')
    expect(status()).toBe('Creating rows')
    await receive(
      runRecord('ai/message', { content: 'Done' }, { cursor: cursor(3) })
    )
    expect(status()).toBe('assistant.statusAnswering')
  })

  test('Stop asks the run to stop and shows it is stopping', async () => {
    const stop = wrapper.find('.assistant__send-button')
    await stop.trigger('click')
    await flushPromises()
    expect(api.cancel).toHaveBeenCalledExactlyOnceWith('run-1')
    expect(stop.element.disabled).toBe(true)
    expect(status()).toBe('assistant.statusStopping')
  })

  test('a native stop from another tab disables Stop and shows it is stopping', async () => {
    await receive({ kind: 'run.cancel_requested', data: {}, cursor: cursor(1) })
    await flushPromises()
    expect(api.cancel).not.toHaveBeenCalled()
    expect(wrapper.find('.assistant__send-button').element.disabled).toBe(true)
    expect(status()).toBe('assistant.statusStopping')
  })

  test('live output loss shows a waiting state for the saved response', async () => {
    await receive(runRecord('chat-run-state', {}, { replay_unavailable: true }))
    expect(status()).toBe('assistant.statusWaitingForOutput')
  })

  test.each(['Partly done', ''])(
    'a durable interrupted outcome %j removes Stop and shows why the answer ended',
    async (content) => {
      await applySnapshot(store, {
        status: 'failed',
        error_code: 'interrupted',
        message: {
          id: 502,
          type: 'ai/message',
          content,
          run_status: 'failed',
          error_code: 'interrupted',
          can_submit_feedback: true,
        },
      })
      await flushPromises()
      const answer = wrapper.findAll('.chat-message').at(-1)
      expect(answer.text()).toContain(content)
      expect(answer.text()).toContain('assistant.runErrorInterrupted')
      expect(answer.find('.chat-message__actions').exists()).toBe(
        Boolean(content)
      )
      expect(wrapper.find('.assistant__disclaimer').exists()).toBe(
        Boolean(content)
      )
      expect(wrapper.find('.iconoir-square').exists()).toBe(false)
    }
  )

  test('closing the panel keeps following the run', async () => {
    wrapper.unmount()
    expect(store.getters['chatRuns/getFollower']('run-1').finished).toBe(false)
    await receive(
      runRecord(
        'ai/reasoning',
        { content: 'Still working' },
        { cursor: cursor(1) }
      )
    )
    expect(store.getters['chatRuns/getFollower']('run-1').view.text).toBe(
      'Still working'
    )
  })
})
