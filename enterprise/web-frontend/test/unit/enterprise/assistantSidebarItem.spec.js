import { nextTick } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, test, vi } from 'vitest'

import AssistantSidebarItem from '@baserow_enterprise/components/assistant/AssistantSidebarItem'

describe('AssistantSidebarItem', () => {
  afterEach(() => {
    localStorage.clear()
    sessionStorage.clear()
  })

  function mountItem({ rightSidebarOpen = false, emit = vi.fn() } = {}) {
    return mountSuspended(AssistantSidebarItem, {
      props: {
        workspace: { id: 1, ai_features: { kuma: { is_enabled: true } } },
        rightSidebarOpen,
      },
      global: {
        mocks: {
          $bus: { $emit: emit },
          $config: { public: { baserowEnterpriseAssistantLlmModel: '' } },
          $hasPermission: () => true,
          $t: (key) => key,
        },
      },
    })
  }

  test('closes an open assistant when the selected workspace disables Kuma', async () => {
    localStorage.setItem('baserow.rightSidebarOpen', 'false')
    const emit = vi.fn()
    const wrapper = await mountItem({ rightSidebarOpen: true, emit })

    await wrapper.setProps({
      workspace: {
        id: 2,
        ai_features: { kuma: { is_enabled: false } },
      },
    })
    await nextTick()

    expect(emit).toHaveBeenCalledWith('toggle-right-sidebar', false)
  })

  test('the tab where the assistant was open reopens it after reloading', async () => {
    localStorage.setItem('baserow.rightSidebarOpen', 'false')
    sessionStorage.setItem('baserow.assistant.panelOpen', 'true')
    const emit = vi.fn()

    await mountItem({ emit })
    await nextTick()

    expect(emit).toHaveBeenCalledWith('toggle-right-sidebar', true)
  })

  test('remembers in the tab whether the assistant is open', async () => {
    const wrapper = await mountItem()

    await wrapper.setProps({ rightSidebarOpen: true })

    expect(sessionStorage.getItem('baserow.assistant.panelOpen')).toBe('true')
  })
})
