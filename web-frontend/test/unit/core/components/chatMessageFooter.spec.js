import { h, nextTick, ref } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import ChatMessageFooter from '@baserow/modules/core/components/chat/ChatMessageFooter'
import { nowKey } from '@baserow/modules/core/composables/useNow'

const timestamp = '2026-11-03T10:00:00Z'

describe('ChatMessageFooter', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
    vi.restoreAllMocks()
  })

  test('keeps copy and optional feedback before the relative time from the shared clock', async () => {
    const now = ref(Date.parse('2026-11-03T10:03:00Z'))
    const wrapper = await testApp.mount(ChatMessageFooter, {
      props: { text: '**Answer**', timestamp },
      slots: {
        default: () => h('button', { type: 'button' }, 'Feedback'),
      },
      global: { provide: { [nowKey]: now } },
    })

    expect([...wrapper.element.children].map((child) => child.tagName)).toEqual(
      ['BUTTON', 'BUTTON', 'TIME']
    )
    expect(wrapper.get('button').attributes('aria-label')).toBe('action.copy')
    expect(wrapper.get('time').attributes('datetime')).toBe(timestamp)
    expect(wrapper.get('time').text()).toBe('datetime.minutesAgo - 3')
    now.value += 60000
    await nextTick()
    expect(wrapper.get('time').text()).toBe('datetime.minutesAgo - 4')
  })

  test.each([undefined, null, '', 'invalid', '2026-02-30T12:00:00Z'])(
    'keeps actions but hides a missing or invalid timestamp %s',
    async (value) => {
      const wrapper = await testApp.mount(ChatMessageFooter, {
        props: { text: 'Answer', timestamp: value },
        slots: { default: () => h('button', { type: 'button' }, 'Feedback') },
      })

      expect(wrapper.findAll('button')).toHaveLength(2)
      expect(wrapper.find('time').exists()).toBe(false)
    }
  )

  test('relays shared copy failures to the caller', async () => {
    const error = new Error('Clipboard denied')
    const writeText = vi
      .spyOn(navigator.clipboard, 'writeText')
      .mockRejectedValue(error)
    const wrapper = await testApp.mount(ChatMessageFooter, {
      props: { text: '**Answer**', timestamp },
    })

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(writeText).toHaveBeenCalledExactlyOnceWith('**Answer**')
    expect(wrapper.emitted('error')).toEqual([[error]])
    expect(wrapper.find('.copied--show').exists()).toBe(false)
  })
})
