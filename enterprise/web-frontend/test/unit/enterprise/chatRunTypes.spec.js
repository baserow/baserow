import { beforeEach, afterEach, describe, expect, test } from 'vitest'
import {
  createRunsTestApp,
  destroyRunsTestApp,
  cursor,
  runRecord,
  followRun,
  acceptRecord,
  applySnapshot,
} from './assistantRunHelpers'
import {
  storeOnboardingRunId,
  storeChatUuid,
  getStoredChatUuid,
  getStoredOnboardingRunId,
} from '@baserow_enterprise/utils/assistantTabStorage'

const uuid = '11111111-1111-4111-8111-111111111111'
const table = { type: 'database-table', database_id: 1, table_id: 2 }
const created = {
  id: 502,
  type: 'ai/message',
  content: 'Created',
  onboarding_target: table,
}

describe('Kuma HTTP record adapter', () => {
  let testApp, store, navigated, unsubscribe
  const navigation = (id, metadata = {}) =>
    runRecord(
      'ai/navigation',
      { location: table },
      { cursor: cursor(id), ...metadata }
    )
  beforeEach(async () => {
    testApp = createRunsTestApp()
    store = testApp.store
    navigated = []
    unsubscribe = store.subscribe(({ type, payload }) => {
      if (type === 'assistant/SET_UI_LOCATION') navigated.push(payload)
    })
    store.commit('assistant/SET_CHATS', [{ uuid, chat_id: 7, title: '' }])
    store.commit('assistant/SET_CURRENT_CHAT_ID', uuid)
    store.commit('assistant/SET_PANEL_OPEN', true)
    await followRun(store)
  })
  afterEach(() => {
    unsubscribe()
    return destroyRunsTestApp(testApp)
  })

  test('cumulative records replace text rather than appending it twice', async () => {
    await acceptRecord(
      store,
      runRecord('ai/reasoning', { content: 'Hel' }, { cursor: cursor(1) })
    )
    await acceptRecord(
      store,
      runRecord('ai/reasoning', { content: 'Hello' }, { cursor: cursor(2) })
    )
    expect(store.getters['assistant/messages'].at(-1)).toMatchObject({
      content: 'Hello',
      reasoning: true,
    })
  })

  test.each([
    ['ai/started', {}, 'queued'],
    ['chat-run-state', { status: 'queued' }, 'queued'],
    ['chat-run-state', { cursor: cursor(1), status: 'running' }, 'running'],
  ])('%s with %j leaves the run %s', async (type, metadata, status) => {
    await acceptRecord(store, runRecord(type, {}, metadata))
    expect(store.getters['chatRuns/getFollower']('run-1').view.status).toBe(
      status
    )
  })

  test('navigation fires only for live output with the panel open', async () => {
    await acceptRecord(store, navigation(1, { replay: true }))
    store.commit('assistant/SET_PANEL_OPEN', false)
    await acceptRecord(store, navigation(2))
    store.commit('assistant/SET_PANEL_OPEN', true)
    await acceptRecord(store, navigation(3))
    expect(navigated).toEqual([table])
  })

  test('a saved answer replaces the live answer by ID', async () => {
    await acceptRecord(
      store,
      runRecord('human', { id: 501, content: 'Hi' }, { cursor: cursor(1) })
    )
    await acceptRecord(
      store,
      runRecord('ai/reasoning', { content: 'Partial' }, { cursor: cursor(2) })
    )
    const message = { id: 502, type: 'ai/message', content: 'Saved' }
    await applySnapshot(store, { status: 'completed', message })
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

  test('a completed onboarding run opens its target in an open panel', async () => {
    storeOnboardingRunId('run-1')
    await applySnapshot(store, { status: 'completed', message: created })
    expect(navigated).toEqual([table])
  })

  test("a saved answer's chat title renames its chat", async () => {
    await applySnapshot(store, {
      status: 'completed',
      message: {
        id: 502,
        type: 'ai/message',
        content: 'Saved',
        chat_title: 'A useful title',
      },
    })

    expect(store.getters['assistant/currentChat'].title).toBe('A useful title')
  })

  test('onboarding completed while closed opens its target once the panel opens', async () => {
    storeOnboardingRunId('run-1')
    const type = testApp.getRegistry().get('chatRunType', 'assistant')
    const follower = store.getters['chatRuns/getFollower']('run-1')
    expect(type.shouldRetainFollower(follower)).toBe(true)
    store.commit('assistant/SET_PANEL_OPEN', false)
    await applySnapshot(store, { status: 'completed', message: created })
    expect(navigated).toEqual([])
    await store.dispatch('assistant/setPanelOpen', true)
    await store.dispatch('assistant/setPanelOpen', true)
    expect(type.shouldRetainFollower(follower)).toBe(false)
    expect(navigated).toEqual([table])
  })

  test('logout forgets the tab conversation and completed onboarding handoff before another login opens the panel', async () => {
    storeChatUuid(uuid)
    storeOnboardingRunId('run-1')
    store.commit('assistant/SET_PANEL_OPEN', false)
    await applySnapshot(store, { status: 'completed', message: created })

    // This is the actual enterprise plugin's auth watcher on TestApp's store.
    store.commit('auth/LOGOFF')
    expect(getStoredChatUuid()).toBeNull()
    expect(getStoredOnboardingRunId()).toBeNull()
    testApp.authenticate({ id: 2, first_name: 'Other' })
    await store.dispatch('assistant/setPanelOpen', true)
    expect(navigated).toEqual([])
  })
})
