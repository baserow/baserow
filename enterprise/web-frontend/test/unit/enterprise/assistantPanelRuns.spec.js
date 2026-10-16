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
} from './chatRuns/runLog'

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
      get: vi.fn().mockResolvedValue({ status: 'running' }),
    }
    coreService.mockReturnValue(api)
    assistantService.mockReturnValue({
      fetchChats: vi.fn().mockResolvedValue({ results: [] }),
      fetchChatMessages: vi.fn().mockResolvedValue({
        chat_id: 7,
        messages: [human],
        active_run: { id: 'run-1', status: 'running' },
      }),
      resumeMessage: vi.fn((chat, run, after, onRecord) => {
        receive = onRecord
        return new Promise(() => {})
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

  test('shows streamed cumulative output and tool progress', async () => {
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
  })

  test('live output loss shows a waiting state for the saved response', async () => {
    await receive(runRecord('chat-run-state', {}, { replay_unavailable: true }))
    expect(status()).toBe('assistant.statusWaitingForOutput')
  })

  test('a durable interrupted outcome removes Stop and shows why the answer ended', async () => {
    await store.dispatch('chatRuns/applySnapshot', {
      runId: 'run-1',
      snapshot: {
        status: 'failed',
        error_code: 'interrupted',
        message: {
          id: 502,
          type: 'ai/message',
          content: 'Partly done',
          run_status: 'failed',
          error_code: 'interrupted',
        },
      },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Partly done')
    expect(wrapper.text()).toContain('assistant.runErrorInterrupted')
    expect(wrapper.find('.iconoir-square').exists()).toBe(false)
  })

  test('closing the panel leaves its stream and status recovery active', async () => {
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
