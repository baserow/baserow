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
})
