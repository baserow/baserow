import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import assistantService from '@baserow_enterprise/services/assistant'
import AssistantPanel from '@baserow_enterprise/components/assistant/AssistantPanel'
import { TestApp } from '@baserow/test/helpers/testApp'

vi.mock('@baserow_enterprise/services/assistant', () => ({
  default: vi.fn(),
}))

const workspace = { id: 1, name: 'Test workspace' }
const otherWorkspace = { id: 2, name: 'Other workspace' }

describe('AssistantPanel', () => {
  let testApp = null
  let store = null
  let service = null
  let resolveCancel = null

  beforeEach(async () => {
    vi.clearAllMocks()
    service = {
      fetchChats: vi.fn().mockResolvedValue({ results: [] }),
      fetchChatMessages: vi.fn().mockResolvedValue({ messages: [] }),
      sendMessage: vi.fn().mockResolvedValue(undefined),
      // Resolved by the test, so a prompt can arrive while cancelling.
      cancelMessage: vi.fn(
        () =>
          new Promise((resolve) => {
            resolveCancel = resolve
          })
      ),
    }
    assistantService.mockReturnValue(service)

    testApp = new TestApp()
    store = testApp.store
    // The welcome message greets the user by name; nothing here needs a session.
    store.state.auth.user = { id: 1, first_name: 'Test' }
    await store.dispatch('workspace/forceCreate', workspace)
    await store.dispatch('workspace/forceCreate', otherWorkspace)
    await store.dispatch('undoRedo/updateCurrentScopeSet', {
      workspace: workspace.id,
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  async function mountWithRunningChat() {
    const wrapper = await testApp.mount(AssistantPanel, {
      props: { workspace },
    })
    await store.dispatch('assistant/createChat', workspace.id)
    const runningChatId = store.getters['assistant/currentChatId']
    store.commit('assistant/SET_ASSISTANT_RUNNING', {
      chat: store.getters['assistant/currentChat'],
      value: true,
    })
    return { wrapper, runningChatId }
  }

  test('sends a pending prompt in a fresh conversation and focuses the input', async () => {
    const { runningChatId } = await mountWithRunningChat()

    await store.dispatch('assistant/setPendingPrompt', 'Build a tracker')
    await flushPromises()
    resolveCancel()
    await flushPromises()

    expect(service.cancelMessage).toHaveBeenCalledWith(runningChatId)
    expect(service.sendMessage).toHaveBeenCalledOnce()
    expect(service.sendMessage.mock.calls[0][0]).not.toBe(runningChatId)
    expect(service.sendMessage.mock.calls[0][1]).toBe('Build a tracker')
    expect(store.getters['assistant/pendingPrompt']).toBe(null)
    expect(document.activeElement.className).toBe('assistant__input-textarea')
  })

  test('drops a pending prompt when the workspace changes while cancelling', async () => {
    const { wrapper } = await mountWithRunningChat()

    await store.dispatch('assistant/setPendingPrompt', 'Build a tracker')
    await flushPromises()
    await wrapper.setProps({ workspace: otherWorkspace })
    resolveCancel()
    await flushPromises()

    expect(service.sendMessage).not.toHaveBeenCalled()
  })

  test('does not fetch chats when the selected workspace goes away', async () => {
    const wrapper = await testApp.mount(AssistantPanel, {
      props: { workspace },
    })

    // The selected workspace getter returns an empty object when none is selected.
    await wrapper.setProps({ workspace: {} })
    await flushPromises()

    expect(service.fetchChats).toHaveBeenCalledOnce()
    expect(service.fetchChats).toHaveBeenCalledWith(workspace.id)
  })

  test('keeps response actions hidden until the chat finishes after its first chunk', async () => {
    const { wrapper } = await mountWithRunningChat()
    store.commit('assistant/SET_MESSAGES', [
      {
        id: 7,
        role: 'ai',
        content: 'Partial response',
        loading: false,
        can_submit_feedback: true,
      },
    ])
    await flushPromises()
    expect(wrapper.get('.chat-message__bubble').attributes('aria-busy')).toBe(
      'true'
    )
    expect(wrapper.find('.chat-message__actions').exists()).toBe(false)

    store.commit('assistant/SET_ASSISTANT_RUNNING', {
      chat: store.getters['assistant/currentChat'],
      value: false,
    })
    await flushPromises()
    expect(wrapper.get('.chat-message__bubble').attributes('aria-busy')).toBe(
      'false'
    )
    expect(wrapper.find('.chat-message__actions').exists()).toBe(true)
  })

  test('updates every message time from the panel clock without requesting messages', async () => {
    vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
    vi.setSystemTime(new Date('2026-11-03T10:03:00Z'))
    const { wrapper } = await mountWithRunningChat()
    store.commit('assistant/SET_ASSISTANT_RUNNING', {
      chat: store.getters['assistant/currentChat'],
      value: false,
    })
    store.commit('assistant/SET_MESSAGES', [
      {
        id: 1,
        role: 'human',
        content: 'Question',
        timestamp: '2026-11-03T10:00:00Z',
      },
      {
        id: 2,
        role: 'ai',
        content: 'Answer',
        timestamp: '2026-11-03T10:00:00Z',
      },
    ])
    await flushPromises()

    expect(wrapper.findAll('time').map((time) => time.text())).toEqual([
      'datetime.minutesAgo - 3',
      'datetime.minutesAgo - 3',
    ])
    await vi.advanceTimersByTimeAsync(60000)
    expect(wrapper.findAll('time').map((time) => time.text())).toEqual([
      'datetime.minutesAgo - 4',
      'datetime.minutesAgo - 4',
    ])
    expect(service.fetchChatMessages).not.toHaveBeenCalled()
  })

  test('ignores invisible thinking growth and follows answer text until the user scrolls up', async () => {
    let xhr
    class FakeXHR {
      constructor() {
        xhr = this
        this.responseText = ''
        this.status = 200
      }
      open() {}
      setRequestHeader() {}
      send() {}
      receive(record) {
        this.responseText += JSON.stringify(record) + '\n\n'
        this.onprogress()
      }
    }
    vi.stubGlobal('XMLHttpRequest', FakeXHR)
    const actualService = await vi.importActual(
      '@baserow_enterprise/services/assistant'
    )
    assistantService.mockImplementation(actualService.default)
    testApp.mock
      .onGet('/assistant/chat/?workspace_id=1')
      .reply(200, { results: [] })
    const wrapper = await testApp.mount(AssistantPanel, {
      props: { workspace },
    })
    const sending = store.dispatch('assistant/sendMessage', {
      message: 'A detailed answer, please',
      workspace,
    })
    await flushPromises()

    const container = wrapper.get('.assistant__content').element
    let height = 1000
    let top = 600
    const writes = []
    vi.spyOn(container, 'scrollHeight', 'get').mockImplementation(() => height)
    vi.spyOn(container, 'clientHeight', 'get').mockReturnValue(400)
    vi.spyOn(container, 'scrollTop', 'get').mockImplementation(() => top)
    vi.spyOn(container, 'scrollTop', 'set').mockImplementation((value) => {
      writes.push(value)
      top = Math.min(value, height - 400)
    })
    const receive = async (record) => {
      xhr.receive(record)
      await flushPromises()
      await new Promise((resolve) => setTimeout(resolve, 0))
    }
    const content = Array.from(
      { length: 40 },
      (_, index) => `Paragraph ${index}: Detailed text.`
    ).join('\n\n')
    await receive({ type: 'ai/reasoning', content })
    expect(wrapper.find('.assistant__reasoning--collapsed').exists()).toBe(true)
    writes.length = 0

    // The preview has reached its cap; more thinking does not change its height.
    await receive({
      type: 'ai/reasoning',
      content: content + '\n\nMore thinking',
    })
    expect(writes).toEqual([])
    height = 1400
    await receive({ type: 'ai/message', content, sources: [] })
    expect(store.getters['assistant/currentChat'].running).toBe(true)
    expect(wrapper.find('.assistant__reasoning--collapsed').exists()).toBe(
      false
    )
    expect(wrapper.find('.assistant__reasoning-toggle').exists()).toBe(false)
    expect(wrapper.findAll('.chat-markdown p')).toHaveLength(40)
    expect(writes).toEqual([1400])

    container.scrollTop = 200
    await wrapper.get('.assistant__content').trigger('scroll')
    writes.length = 0
    height = 1600
    const final = content + '\n\nThe final paragraph.'
    await receive({ type: 'ai/message', content: final, sources: [] })
    await receive({
      type: 'ai/message',
      id: 7,
      content: final,
      sources: [],
      can_submit_feedback: true,
    })
    xhr.onload()
    await sending
    await flushPromises()

    expect(writes).toEqual([])
    expect(top).toBe(200)
    expect(wrapper.findAll('.chat-markdown p')).toHaveLength(41)
    expect(wrapper.find('.assistant__reasoning-toggle').exists()).toBe(false)
    expect(wrapper.find('button[aria-label="action.copy"]').exists()).toBe(true)
    expect(store.getters['assistant/currentChat'].running).toBe(false)
  })
})
