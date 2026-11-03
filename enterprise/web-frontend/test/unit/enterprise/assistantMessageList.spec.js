import { flushPromises } from '@vue/test-utils'
import { routerKey } from 'vue-router'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import AssistantMessageList from '@baserow_enterprise/components/assistant/AssistantMessageList'
import assistantService from '@baserow_enterprise/services/assistant'

vi.mock('@baserow_enterprise/services/assistant', () => ({ default: vi.fn() }))

const answer = (extra = {}) => ({
  id: 7,
  role: 'ai',
  content: '**Answer**',
  loading: false,
  can_submit_feedback: true,
  ...extra,
})
const copy = (wrapper) => wrapper.get('button[aria-label="action.copy"]')

describe('AssistantMessageList', () => {
  let testApp, service

  beforeEach(() => {
    testApp = new TestApp()
    service = { submitFeedback: vi.fn().mockResolvedValue() }
    assistantService.mockReturnValue(service)
  })

  afterEach(async () => {
    await testApp.afterEach()
    vi.restoreAllMocks()
  })

  test('keeps the shared bubble while waiting, reasoning and streaming the final answer', async () => {
    const pending = answer({
      id: 'temporary',
      _uuid: 'reply-uuid',
      content: '',
      loading: true,
      can_submit_feedback: false,
    })
    const wrapper = await testApp.mount(AssistantMessageList, {
      props: { messages: [pending], running: true },
    })
    const bubble = wrapper.get('.chat-message__bubble').element
    expect(wrapper.findAll('.chat-typing__dot')).toHaveLength(3)
    expect(wrapper.find('.chat-message__actions').exists()).toBe(false)

    const reasoning = {
      ...pending,
      id: 7,
      content: '**Plan**',
      loading: false,
      reasoning: true,
    }
    await wrapper.setProps({ messages: [reasoning] })

    expect(wrapper.get('.chat-message__bubble').element).toBe(bubble)
    expect(wrapper.get('.chat-markdown strong').text()).toBe('Plan')
    expect(wrapper.get('.chat-message__bubble').attributes('aria-busy')).toBe(
      'true'
    )
    expect(wrapper.find('.chat-typing').exists()).toBe(false)
    expect(wrapper.find('.loading').exists()).toBe(false)
    expect(wrapper.find('.chat-message__actions').exists()).toBe(false)
    const toggle = wrapper.get('.assistant__reasoning-toggle')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(
      wrapper.get(`#${toggle.attributes('aria-controls')}`).classes()
    ).toContain('assistant__reasoning--collapsed')
    await toggle.trigger('click')
    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('.chat-markdown').classes()).not.toContain(
      'assistant__reasoning--collapsed'
    )

    const final = answer({
      _uuid: pending._uuid,
      sources: ['https://example.com/source'],
    })
    await wrapper.setProps({ messages: [final] })
    expect(wrapper.get('.chat-message__bubble').element).toBe(bubble)
    expect(wrapper.get('.chat-markdown strong').text()).toBe('Answer')
    expect(wrapper.find('.assistant__reasoning-toggle').exists()).toBe(false)
    expect(wrapper.find('.chat-message__actions').exists()).toBe(false)
    await wrapper.setProps({ running: false })

    expect(wrapper.get('.chat-message__bubble').attributes('aria-busy')).toBe(
      'false'
    )
    expect(copy(wrapper).exists()).toBe(true)
    expect(wrapper.findAll('.assistant__feedback-button')).toHaveLength(2)
    expect(wrapper.get('.assistant__disclaimer').text()).toBe(
      'assistantMessageList.disclaimer'
    )
    const sources = wrapper.get('.assistant__sources-toggle')
    expect(sources.attributes('aria-expanded')).toBe('false')
    await sources.trigger('click')
    expect(sources.attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('.assistant__source-link').attributes('href')).toBe(
      'https://example.com/source'
    )
  })

  test('uses the shared own-message style and copies human text without formatting it', async () => {
    const content = '**Literal**\n<img src="https://example.com/image.png">'
    const writeText = vi
      .spyOn(navigator.clipboard, 'writeText')
      .mockResolvedValue()
    const wrapper = await testApp.mount(AssistantMessageList, {
      props: {
        messages: [
          { id: 1, role: 'human', content },
          answer({ can_submit_feedback: false }),
        ],
      },
    })
    const own = wrapper.get('.chat-message--own')
    expect(own.get('.chat-message__bubble').element.textContent).toBe(content)
    expect(own.find('strong').exists()).toBe(false)
    expect(own.find('img').exists()).toBe(false)
    expect(wrapper.findAll('button[aria-label="action.copy"]')).toHaveLength(2)
    expect(wrapper.find('.assistant__feedback').exists()).toBe(false)
    expect(wrapper.find('.assistant__disclaimer').exists()).toBe(false)
    await copy(own).trigger('click')
    await flushPromises()
    expect(writeText).toHaveBeenCalledExactlyOnceWith(content)
    expect(own.find('.copied--show').exists()).toBe(true)
    expect(testApp.store.state.toast.items).toEqual([])
  })

  test('uses shared markdown safety and link navigation', async () => {
    const router = { resolve: vi.fn(() => ({ matched: [{}] })), push: vi.fn() }
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    const wrapper = await testApp.mount(AssistantMessageList, {
      props: {
        messages: [
          answer({
            content:
              '[App](/database/1/table/2?view=3#row) [Site](https://example.com/page)\n\n![image](https://evil.test/image) <img src="https://evil.test/html">',
          }),
        ],
      },
      global: { provide: { [routerKey]: router } },
    })
    expect(wrapper.find('img').exists()).toBe(false)
    const [appLink, siteLink] = wrapper.findAll('.chat-markdown a')
    await appLink.trigger('click')
    expect(router.push).toHaveBeenCalledExactlyOnceWith(
      '/database/1/table/2?view=3#row'
    )
    await siteLink.trigger('click')
    expect(open).toHaveBeenCalledExactlyOnceWith(
      'https://example.com/page',
      '_blank',
      'noopener,noreferrer'
    )
    const modified = new MouseEvent('click', {
      bubbles: true,
      cancelable: true,
      ctrlKey: true,
    })
    appLink.element.dispatchEvent(modified)
    expect(modified.defaultPrevented).toBe(false)
    expect(router.push).toHaveBeenCalledTimes(1)
  })

  test('keeps raw response copy separate from sources and reports clipboard failure', async () => {
    const content = '**Response**'
    const writeText = vi
      .spyOn(navigator.clipboard, 'writeText')
      .mockRejectedValue(new Error('Clipboard denied'))
    const wrapper = await testApp.mount(AssistantMessageList, {
      props: {
        messages: [
          answer({ content, sources: ['https://example.com/source'] }),
        ],
      },
    })
    await copy(wrapper).trigger('click')
    await flushPromises()
    expect(writeText).toHaveBeenCalledExactlyOnceWith(content)
    expect(wrapper.find('.copied--show').exists()).toBe(false)
    expect(testApp.store.state.toast.items).toEqual([
      expect.objectContaining({
        type: 'error',
        title: 'assistantMessageActions.copyFailed',
      }),
    ])
  })

  test('keeps helpful and detailed negative feedback on the existing service', async () => {
    testApp.store.commit('assistant/SET_MESSAGES', [answer()])
    const wrapper = await testApp.mount(AssistantMessageList, {
      props: { messages: testApp.store.getters['assistant/messages'] },
    })
    const updateMessages = () =>
      wrapper.setProps({
        messages: testApp.store.getters['assistant/messages'],
      })
    await wrapper
      .get('button[aria-label="assistantMessageActions.helpful"]')
      .trigger('click')
    await flushPromises()
    expect(service.submitFeedback).toHaveBeenLastCalledWith(
      7,
      'LIKE',
      undefined
    )
    await updateMessages()
    expect(
      wrapper
        .get('.assistant__feedback-button--thumb-up')
        .attributes('aria-pressed')
    ).toBe('true')
    expect(
      wrapper.find('.assistant__feedback-button--thumb-down').exists()
    ).toBe(false)
    await wrapper.get('.assistant__feedback-button--thumb-up').trigger('click')
    await flushPromises()
    expect(service.submitFeedback).toHaveBeenLastCalledWith(7, null, undefined)
    await updateMessages()
    await wrapper
      .get('button[aria-label="assistantMessageActions.notHelpful"]')
      .trigger('click')
    await flushPromises()
    expect(service.submitFeedback).toHaveBeenLastCalledWith(
      7,
      'DISLIKE',
      undefined
    )
    const feedback = wrapper.get('.assistant__feedback-context textarea')
    await feedback.setValue('  Please be more specific  ')
    await feedback.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(service.submitFeedback).toHaveBeenLastCalledWith(
      7,
      'DISLIKE',
      'Please be more specific'
    )
  })

  test('preserves error and cancelled outcomes with shared styles', async () => {
    const wrapper = await testApp.mount(AssistantMessageList, {
      props: {
        messages: [
          answer({
            id: 1,
            content: 'Failed',
            error: true,
            can_submit_feedback: false,
          }),
          answer({
            id: 2,
            content: 'Message cancelled',
            cancelled: true,
            can_submit_feedback: false,
          }),
        ],
        running: true,
      },
    })
    expect(wrapper.get('.chat-message__bubble--error').text()).toBe('Failed')
    expect(wrapper.get('.chat-message__note').text()).toBe('Message cancelled')
    expect(wrapper.find('.assistant__feedback').exists()).toBe(false)
    expect(wrapper.find('.assistant__disclaimer').exists()).toBe(false)
    expect(wrapper.findAll('button[aria-label="action.copy"]')).toHaveLength(2)
    expect(wrapper.find('[aria-busy="true"]').exists()).toBe(false)
  })
})
