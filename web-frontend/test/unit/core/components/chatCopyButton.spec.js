import { afterEach, describe, expect, test, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ChatCopyButton from '@baserow/modules/core/components/chat/ChatCopyButton'
import Copied from '@baserow/modules/core/components/Copied'

const render = () =>
  mount(ChatCopyButton, {
    props: { text: '**Hello**' },
    global: {
      components: { Copied },
      directives: { tooltip: {} },
      mocks: { $t: (key) => key },
    },
  })

describe('ChatCopyButton', () => {
  afterEach(() => vi.restoreAllMocks())

  test('copies the original text and shows confirmation', async () => {
    const writeText = vi
      .spyOn(navigator.clipboard, 'writeText')
      .mockResolvedValue()
    const wrapper = render()

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(writeText).toHaveBeenCalledExactlyOnceWith('**Hello**')
    expect(wrapper.find('.copied--show').exists()).toBe(true)
    wrapper.unmount()
  })

  test('lets the caller handle clipboard failure without showing success', async () => {
    const error = new Error('Clipboard denied')
    vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValue(error)
    const wrapper = render()

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('error')).toEqual([[error]])
    expect(wrapper.find('.copied--show').exists()).toBe(false)
    wrapper.unmount()
  })

  test('allows a copy to finish after the message was unmounted', async () => {
    let finish
    vi.spyOn(navigator.clipboard, 'writeText').mockImplementation(
      () => new Promise((resolve) => (finish = resolve))
    )
    const wrapper = render()
    await wrapper.get('button').trigger('click')
    wrapper.unmount()

    finish()
    await flushPromises()

    expect(wrapper.emitted('error')).toBeUndefined()
  })
})
