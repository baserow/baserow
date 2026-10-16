import { beforeEach, afterEach, describe, expect, test, vi } from 'vitest'
import {
  createRunsTestApp,
  destroyRunsTestApp,
  cursor,
  runRecord,
} from './chatRuns/runLog'
import {
  getTabId,
  storeOnboardingRunId,
  storeChatUuid,
  getStoredChatUuid,
  getStoredOnboardingRunId,
} from '@baserow_enterprise/utils/assistantTabStorage'

const uuid = '11111111-1111-4111-8111-111111111111'
const table = { type: 'database-table', database_id: 1, table_id: 2 }

describe('Kuma HTTP record adapter', () => {
  let testApp, store
  const accept = (record) =>
    store.dispatch('chatRuns/acceptRecord', { runId: 'run-1', record })
  const navigation = (id, metadata = {}, origin = getTabId()) =>
    runRecord(
      'ai/navigation',
      {
        location: table,
        origin_tab_id: origin,
      },
      { cursor: cursor(id), ...metadata }
    )
  beforeEach(async () => {
    testApp = createRunsTestApp()
    store = testApp.store
    store.commit('assistant/SET_CHATS', [{ uuid, chat_id: 7, title: '' }])
    store.commit('assistant/SET_CURRENT_CHAT_ID', uuid)
    store.commit('assistant/SET_PANEL_OPEN', true)
    await store.dispatch('chatRuns/follow', {
      runId: 'run-1',
      runType: 'assistant',
      chatId: 7,
      attach: false,
    })
  })
  afterEach(() => destroyRunsTestApp(testApp))

  test('cumulative records replace text rather than appending it twice', async () => {
    await accept(
      runRecord('ai/reasoning', { content: 'Hel' }, { cursor: cursor(1) })
    )
    await accept(
      runRecord('ai/reasoning', { content: 'Hello' }, { cursor: cursor(2) })
    )
    expect(store.getters['assistant/messages'].at(-1)).toMatchObject({
      content: 'Hello',
      reasoning: true,
    })
  })

  test('navigation fires once only for new live output in the origin tab with its panel open', async () => {
    await accept(navigation(1, { replay: true }))
    await accept(navigation(2, {}, 'other-tab'))
    store.commit('assistant/SET_PANEL_OPEN', false)
    await accept(navigation(3))
    store.commit('assistant/SET_PANEL_OPEN', true)
    await accept(navigation(4))
    await accept(navigation(4))
    await accept(navigation(5, { replay: true })) // reconnect catch-up in origin tab
    expect(store.getters['assistant/uiLocationHistory']).toEqual([table])
  })

  test('reset baselines rebuild text without navigation effects', async () => {
    await accept(
      runRecord('ai/reasoning', { content: 'Old' }, { cursor: cursor(1) })
    )
    await accept(
      runRecord(
        'ai/message',
        { content: 'Replacement' },
        { cursor: 'new:1-0', reset: true, replay: true }
      )
    )
    expect(store.getters['assistant/messages'].at(-1).content).toBe(
      'Replacement'
    )
    expect(store.getters['assistant/uiLocationHistory']).toEqual([])
  })

  test('saved messages replace the live view by ID and terminal snapshots cannot be reopened', async () => {
    await accept(
      runRecord('human', { id: 501, content: 'Hi' }, { cursor: cursor(1) })
    )
    await accept(
      runRecord('ai/reasoning', { content: 'Partial' }, { cursor: cursor(2) })
    )
    const message = { id: 502, type: 'ai/message', content: 'Saved' }
    await store.dispatch('chatRuns/applySnapshot', {
      runId: 'run-1',
      snapshot: { status: 'completed', message },
    })
    await accept(
      runRecord('ai/reasoning', { content: 'Late' }, { cursor: cursor(3) })
    )
    expect(
      store.getters['assistant/messages'].map(({ id, content }) => [
        id,
        content,
      ])
    ).toEqual([
      [501, 'Hi'],
      [502, 'Saved'],
    ])
  })

  test('onboarding opens its durable completion target after Redis output is lost', async () => {
    storeOnboardingRunId('run-1')
    await store.dispatch('chatRuns/applySnapshot', {
      runId: 'run-1',
      snapshot: {
        status: 'completed',
        message: {
          id: 502,
          type: 'ai/message',
          content: 'Created',
          artifacts: { onboarding_target: table },
        },
      },
    })
    expect(store.getters['assistant/uiLocationHistory']).toEqual([table])
  })

  test('the durable terminal answer restores the chat title after Redis output is lost', async () => {
    await accept(runRecord('chat-run-state', {}, { replay_unavailable: true }))
    await store.dispatch('chatRuns/applySnapshot', {
      runId: 'run-1',
      snapshot: {
        status: 'completed',
        message: {
          id: 502,
          type: 'ai/message',
          content: 'Saved',
          chat_title: 'A useful title',
        },
      },
    })

    expect(store.getters['assistant/currentChat'].title).toBe('A useful title')
    expect(store.getters['assistant/messages'].at(-1).content).toBe('Saved')
  })

  test('onboarding completed while closed opens its target once the panel opens', async () => {
    storeOnboardingRunId('run-1')
    const type = testApp.getRegistry().get('chatRunType', 'assistant')
    const follower = store.getters['chatRuns/getFollower']('run-1')
    expect(type.shouldRetainFollower(follower)).toBe(true)
    store.commit('assistant/SET_PANEL_OPEN', false)
    await store.dispatch('chatRuns/applySnapshot', {
      runId: 'run-1',
      snapshot: {
        status: 'completed',
        message: {
          id: 502,
          type: 'ai/message',
          content: 'Created',
          onboarding_target: table,
        },
      },
    })
    expect(store.getters['assistant/uiLocationHistory']).toEqual([])
    await store.dispatch('assistant/setPanelOpen', true)
    await store.dispatch('assistant/setPanelOpen', true)
    expect(type.shouldRetainFollower(follower)).toBe(false)
    expect(store.getters['assistant/uiLocationHistory']).toEqual([table])
  })

  test('logout forgets the tab conversation and completed onboarding handoff before another login opens the panel', async () => {
    storeChatUuid(uuid)
    storeOnboardingRunId('run-1')
    store.commit('assistant/SET_PANEL_OPEN', false)
    await store.dispatch('chatRuns/applySnapshot', {
      runId: 'run-1',
      snapshot: {
        status: 'completed',
        message: {
          id: 502,
          type: 'ai/message',
          content: 'Created',
          onboarding_target: table,
        },
      },
    })

    // This is the actual enterprise plugin's auth watcher on TestApp's store.
    store.commit('auth/LOGOFF')
    expect(getStoredChatUuid()).toBeNull()
    expect(getStoredOnboardingRunId()).toBeNull()
    testApp.authenticate({ id: 2, first_name: 'Other' })
    await store.dispatch('assistant/setPanelOpen', true)
    expect(store.getters['assistant/uiLocationHistory']).toEqual([])
  })

  test('worker loss without partial text still explains the interrupted turn', async () => {
    await store.dispatch('chatRuns/applySnapshot', {
      runId: 'run-1',
      snapshot: { status: 'failed', error_code: 'interrupted', message: null },
    })
    expect(store.getters['assistant/messages'].at(-1)).toMatchObject({
      content: '',
      run_status: 'failed',
      error_code: 'interrupted',
    })
  })
})
