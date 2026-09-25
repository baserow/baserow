import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, test, vi } from 'vitest'

import AssistantDashboardPrompt from '@baserow_enterprise/components/assistant/AssistantDashboardPrompt'

const workspace = { id: 1, ai_features: { kuma: { is_enabled: true } } }

async function mount({
  workspace: value = workspace,
  hasPermission = () => true,
  dispatch = vi.fn(),
  emit = vi.fn(),
} = {}) {
  const wrapper = await mountSuspended(AssistantDashboardPrompt, {
    attachTo: document.body,
    props: { workspace: value },
    global: {
      mocks: {
        $bus: { $emit: emit },
        $config: { public: { baserowEnterpriseAssistantLlmModel: '' } },
        $hasPermission: hasPermission,
        $store: { dispatch },
        $t: (key) => key,
      },
    },
  })
  return { wrapper, dispatch, emit }
}

describe('AssistantDashboardPrompt', () => {
  test('renders when the assistant is available', async () => {
    const { wrapper } = await mount()

    expect(wrapper.find('.assistant-prompt').exists()).toBe(true)
  })

  test('renders nothing without the permission to chat', async () => {
    const { wrapper } = await mount({ hasPermission: () => false })

    expect(wrapper.find('.assistant-prompt').exists()).toBe(false)
  })

  test('renders nothing when the workspace has the assistant disabled', async () => {
    const { wrapper } = await mount({
      workspace: { id: 2, ai_features: { kuma: { is_enabled: false } } },
    })

    expect(wrapper.find('.assistant-prompt').exists()).toBe(false)
  })

  test('hands the message over and opens the assistant', async () => {
    const { wrapper, dispatch, emit } = await mount()
    await wrapper.find('input').setValue('  Create an asset tracker  ')

    await wrapper.find('button').trigger('click')

    expect(dispatch).toHaveBeenCalledWith(
      'assistant/setPendingPrompt',
      'Create an asset tracker'
    )
    expect(emit).toHaveBeenCalledWith('toggle-right-sidebar', true)
    // The box is left empty, so returning to it doesn't resend the same thing.
    expect(wrapper.find('input').element.value).toBe('')
  })

  test('enter hands over without leaving the focus or a newline behind', async () => {
    const { wrapper, dispatch } = await mount()
    const input = wrapper.find('input')
    await input.setValue('Create an asset tracker')
    input.element.focus()

    // A real event, so the default action can be checked: the panel takes the
    // focus straight after, and the key press would otherwise land there.
    const event = new KeyboardEvent('keydown', {
      key: 'Enter',
      bubbles: true,
      cancelable: true,
    })
    input.element.dispatchEvent(event)
    await flushPromises()

    expect(dispatch).toHaveBeenCalledOnce()
    expect(event.defaultPrevented).toBe(true)
    expect(document.activeElement).not.toBe(input.element)
  })

  test('does nothing while the box is empty', async () => {
    const { wrapper, dispatch, emit } = await mount()
    await wrapper.find('input').setValue('   ')

    await wrapper.find('button').trigger('click')

    expect(dispatch).not.toHaveBeenCalled()
    expect(emit).not.toHaveBeenCalled()
  })
})
