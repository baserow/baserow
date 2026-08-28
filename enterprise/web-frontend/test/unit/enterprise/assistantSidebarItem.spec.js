import { nextTick } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, test, vi } from 'vitest'

import AssistantSidebarItem from '@baserow_enterprise/components/assistant/AssistantSidebarItem'

describe('AssistantSidebarItem', () => {
  afterEach(() => {
    localStorage.clear()
  })

  test('closes an open assistant when the selected workspace disables Kuma', async () => {
    localStorage.setItem('baserow.rightSidebarOpen', 'false')
    const emit = vi.fn()
    const wrapper = await mountSuspended(AssistantSidebarItem, {
      props: {
        workspace: {
          id: 1,
          ai_features: { kuma: { is_enabled: true } },
        },
        rightSidebarOpen: true,
      },
      global: {
        mocks: {
          $bus: { $emit: emit },
          $config: {
            public: { baserowEnterpriseAssistantLlmModel: '' },
          },
          $hasPermission: () => true,
          $t: (key) => key,
        },
      },
    })

    await wrapper.setProps({
      workspace: {
        id: 2,
        ai_features: { kuma: { is_enabled: false } },
      },
    })
    await nextTick()

    expect(emit).toHaveBeenCalledWith('toggle-right-sidebar', false)
  })
})
