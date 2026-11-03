import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import ChatComposer from '@baserow/modules/core/components/chat/ChatComposer'

describe('ChatComposer', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountComposer = (props) =>
    testApp.mount(ChatComposer, {
      props: {
        modelValue: 'Hello',
        canSend: true,
        sendLabel: 'Send',
        stopLabel: 'Stop',
        ...props,
      },
    })

  test.each([false, true])(
    'sends with Enter or submit only when enabled, disabled: %s',
    async (disabled) => {
      const wrapper = await mountComposer({ disabled })
      const textarea = wrapper.get('textarea')
      const submit = wrapper.get('button[type="submit"]')

      textarea.element.dispatchEvent(
        new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })
      )
      await wrapper.get('form').trigger('submit')

      expect(wrapper.emitted('send') ?? []).toHaveLength(disabled ? 0 : 2)
      expect(textarea.element.disabled).toBe(disabled)
      expect(submit.element.disabled).toBe(disabled)
      expect(submit.classes('chat-composer__button--ready')).toBe(!disabled)
    }
  )

  test('shows a waiting activity in its own tone, which an error replaces', async () => {
    const wrapper = await mountComposer({ activity: 'Thinking' })
    const activity = () => wrapper.get('.chat-composer__activity')

    expect(activity().classes()).not.toContain(
      'chat-composer__activity--waiting'
    )
    expect(activity().find('.iconoir-sparks').exists()).toBe(true)

    await wrapper.setProps({ activity: 'Waiting', activityTone: 'waiting' })
    expect(activity().classes()).toEqual(
      expect.arrayContaining([
        'chat-composer__activity--visible',
        'chat-composer__activity--waiting',
      ])
    )
    expect(activity().find('.iconoir-shield-check').exists()).toBe(true)
    expect(activity().text()).toBe('Waiting')

    await wrapper.setProps({ error: 'Failed to send' })
    expect(activity().classes()).toContain('chat-composer__activity--error')
    expect(activity().classes()).not.toContain(
      'chat-composer__activity--waiting'
    )
    expect(activity().find('.iconoir-warning-circle').exists()).toBe(true)
  })
})
