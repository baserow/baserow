import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import AgentConversationList from '@baserow/modules/agent/components/AgentConversationList'
import { flushPromises } from '@vue/test-utils'
import { chooseFromMenu } from './helpers'

describe('Agent conversation list', () => {
  let testApp, form

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
    form?.remove()
    form = null
  })

  test('activates conversations and shared actions without submitting an enclosing form', async () => {
    const conversation = { uuid: 'saved', title: 'Saved conversation' }
    const wrapper = await testApp.mount(AgentConversationList, {
      props: {
        items: [conversation],
        hasMore: true,
        canCreate: true,
        readyToSend: true,
      },
    })
    form = document.createElement('form')
    const submit = vi.fn((event) => event.preventDefault())
    form.addEventListener('submit', submit)
    document.body.appendChild(form)
    form.appendChild(wrapper.element)

    wrapper.get('.agent-conversations__item').element.click()
    await wrapper.get('.agent-conversations__content').trigger('scroll')
    wrapper.get('.agent-conversations__footer button').element.click()
    await wrapper.setProps({ error: true })
    wrapper.get('.alert button').element.click()

    expect(submit).not.toHaveBeenCalled()
    expect(wrapper.emitted('select')).toEqual([[conversation]])
    for (const action of ['load-more', 'create', 'retry']) {
      expect(wrapper.emitted(action)).toHaveLength(1)
    }
  })

  test('retains focus and selection while existing rows load or reorder', async () => {
    const saved = { uuid: 'saved', title: 'Saved conversation' }
    const draft = { uuid: 'draft', title: '', local: true }
    const wrapper = await testApp.mount(AgentConversationList, {
      props: { items: [saved, draft], selected: 'saved', hasMore: true },
    })
    const selected = wrapper.get('[aria-current="true"]')
    selected.element.focus()

    await wrapper.setProps({ loading: true, items: [draft, saved] })
    await wrapper.get('.agent-conversations__content').trigger('scroll')

    expect(wrapper.get('[aria-current="true"]').element).toBe(selected.element)
    expect(document.activeElement).toBe(selected.element)
    expect(wrapper.findAll('.agent-conversations__row')).toHaveLength(2)
    expect(wrapper.get('.agent-conversations__draft').text()).toBe(
      'agent.draft'
    )
    expect(wrapper.find('.skeleton').exists()).toBe(false)
    expect(wrapper.emitted('load-more')).toBeUndefined()
  })

  test('keeps the creation control focused as an empty list finishes loading and gains a draft', async () => {
    const wrapper = await testApp.mount(AgentConversationList, {
      props: { items: [], loading: true, canCreate: true, readyToSend: true },
    })
    const create = wrapper.get('.agent-conversations__footer button')
    const header = wrapper.get('.agent-conversations__header')
    const content = wrapper.get('.agent-conversations__content')
    create.element.focus()
    expect(wrapper.find('.skeleton').exists()).toBe(true)

    await wrapper.setProps({ loading: false })
    expect(wrapper.get('.agent-conversations__header').element).toBe(
      header.element
    )
    expect(wrapper.get('.agent-conversations__content').element).toBe(
      content.element
    )
    expect(wrapper.find('.skeleton').exists()).toBe(false)
    expect(document.activeElement).toBe(create.element)

    await wrapper.setProps({ error: true })
    expect(wrapper.find('.alert').exists()).toBe(true)
    expect(wrapper.find('.agent-conversations__header').exists()).toBe(true)

    await wrapper.setProps({
      error: false,
      items: [{ uuid: 'draft', title: '', local: true }],
    })
    const row = wrapper.get('.agent-conversations__item')
    expect(row.get('.iconoir-chat-bubble').exists()).toBe(true)
    expect(row.element.lastElementChild).toBe(
      row.get('.agent-conversations__status').element
    )
    expect(row.get('.agent-conversations__draft').text()).toBe('agent.draft')
    expect(wrapper.get('.agent-conversations__footer button').element).toBe(
      create.element
    )
    expect(document.activeElement).toBe(create.element)
    create.element.click()
    expect(wrapper.emitted('create')).toHaveLength(1)
  })

  test('keeps an empty Recent section visible without creation permission', async () => {
    const wrapper = await testApp.mount(AgentConversationList, {
      props: { items: [] },
    })

    expect(wrapper.get('.agent-conversations__header').text()).toBe(
      'agent.recent'
    )
    expect(wrapper.get('.agent-conversations__content').isVisible()).toBe(true)
    expect(wrapper.get('aside').attributes('aria-hidden')).toBeUndefined()
    expect(wrapper.find('.agent-conversations__footer').exists()).toBe(false)
  })

  test('marks a conversation waiting for approval with a labelled dot', async () => {
    const wrapper = await testApp.mount(AgentConversationList, {
      props: {
        items: [
          { uuid: 'waiting', title: 'Waiting', pending_approval_count: 2 },
          { uuid: 'replying', title: 'Replying', run_id: 'run-1' },
        ],
      },
    })
    const [waiting, replying] = wrapper.findAll('.agent-conversations__item')

    expect(waiting.get('.agent-conversations__status').classes()).toContain(
      'agent-conversations__status--waiting'
    )
    expect(waiting.get('.agent-conversations__status-label').text()).toBe(
      'agent.waitingForApproval'
    )
    expect(replying.get('.agent-conversations__status').classes()).toContain(
      'agent-conversations__status--replying'
    )
    expect(replying.find('.agent-conversations__status-label').exists()).toBe(
      false
    )
  })

  const mountList = (items) =>
    testApp.mount(AgentConversationList, {
      props: { items, canUpdate: true, canDelete: true },
    })
  const saved = { uuid: 'saved', title: 'Saved conversation' }

  test('offers a menu only for saved conversations and cancels a rename on Escape', async () => {
    const wrapper = await mountList([
      saved,
      { uuid: 'draft', title: '', local: true },
    ])
    const [, draftRow] = wrapper.findAll('.agent-conversations__row')
    expect(draftRow.find('.agent-conversations__options').exists()).toBe(false)

    await chooseFromMenu(wrapper, 'Saved conversation', 'action.rename')
    const input = wrapper.get('.agent-conversations__rename')
    await input.setValue('Unsaved title')
    await input.trigger('keydown', { key: 'Escape' })
    await flushPromises()

    expect(wrapper.find('.agent-conversations__rename').exists()).toBe(false)
    expect(document.activeElement).toBe(
      wrapper.get('.agent-conversations__item').element
    )
    expect(wrapper.emitted('update')).toBeUndefined()
  })

  test('saves only a typed title, not on an input method Enter or after a removal', async () => {
    const wrapper = await mountList([saved])
    const rename = async (title) => {
      await chooseFromMenu(wrapper, title, 'action.rename')
      return wrapper.get('.agent-conversations__rename')
    }

    let input = await rename('Saved conversation')
    await wrapper.setProps({
      items: [{ ...saved, title: 'Renamed elsewhere' }],
    })
    await input.trigger('blur')
    input = await rename('Renamed elsewhere')
    await input.setValue('Typed')
    await input.trigger('keydown', { key: 'Enter', isComposing: true })
    expect(wrapper.find('.agent-conversations__rename').exists()).toBe(true)
    await wrapper.setProps({ items: [] })
    await flushPromises()

    expect(wrapper.emitted('update')).toBeUndefined()
  })

  test('keeps the row being renamed in place until the rename ends', async () => {
    const other = { uuid: 'other', title: 'Other conversation' }
    const wrapper = await mountList([other, saved])
    const rows = () =>
      wrapper.findAll('.agent-conversations__row').map(({ element }) => element)
    await chooseFromMenu(wrapper, 'Saved conversation', 'action.rename')
    const [, renaming] = rows()

    await wrapper.setProps({ items: [saved, other] })
    expect(rows()[1]).toBe(renaming)

    const input = wrapper.get('.agent-conversations__rename')
    await input.setValue('Renamed')
    await input.trigger('keydown', { key: 'Enter' })
    expect(rows()[0]).toBe(renaming)
    expect(wrapper.emitted('update')).toEqual([[saved, { title: 'Renamed' }]])
  })

  test('fills a tall viewport, pauses on error, and disconnects its observer', async () => {
    let intersect
    const disconnect = vi.fn()
    vi.stubGlobal(
      'IntersectionObserver',
      class {
        constructor(callback) {
          intersect = callback
        }
        observe() {}
        unobserve() {}
        disconnect() {
          disconnect()
        }
      }
    )
    try {
      const wrapper = await mountList([saved])
      await wrapper.setProps({ hasMore: true })
      intersect([{ isIntersecting: true }])
      expect(wrapper.emitted('load-more')).toHaveLength(1)
      await wrapper.setProps({ loading: true })
      intersect([{ isIntersecting: true }])
      await wrapper.setProps({ loading: false, error: true })
      intersect([{ isIntersecting: true }])
      expect(wrapper.emitted('load-more')).toHaveLength(1)
      expect(
        wrapper.get('.agent-conversations__private').attributes('aria-label')
      ).toBe('agent.privateConversation')
      wrapper.unmount()
      expect(disconnect).toHaveBeenCalledOnce()
    } finally {
      vi.unstubAllGlobals()
    }
  })
})
