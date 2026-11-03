import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import AgentConversationList from '@baserow/modules/agent/components/AgentConversationList'
import Context from '@baserow/modules/core/components/Context'

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
    wrapper.get('.agent-conversations__more').element.click()
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
    const more = wrapper.get('.agent-conversations__more')
    more.element.click()

    expect(wrapper.get('[aria-current="true"]').element).toBe(selected.element)
    expect(document.activeElement).toBe(selected.element)
    expect(wrapper.findAll('li')).toHaveLength(2)
    expect(wrapper.get('.agent-conversations__draft').text()).toBe(
      'agent.draft'
    )
    expect(wrapper.find('.skeleton').exists()).toBe(false)
    expect(more.element.disabled).toBe(true)
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

  test('offers a menu only for saved conversations and cancels a rename on Escape', async () => {
    const wrapper = await testApp.mount(AgentConversationList, {
      props: {
        items: [
          { uuid: 'saved', title: 'Saved conversation' },
          { uuid: 'draft', title: '', local: true },
        ],
        canRename: true,
        canDelete: true,
      },
    })
    const [saved, draft] = wrapper.findAll('.agent-conversations__row')
    expect(draft.find('.agent-conversations__options').exists()).toBe(false)

    await saved.get('.agent-conversations__options').trigger('click')
    await wrapper
      .findComponent(Context)
      .get('.context__menu-item-link')
      .trigger('click')
    const input = wrapper.get('.agent-conversations__rename')
    await input.setValue('Unsaved title')
    await input.trigger('keydown', { key: 'Escape' })

    expect(wrapper.find('.agent-conversations__rename').exists()).toBe(false)
    expect(wrapper.get('.agent-conversations__item').text()).toBe(
      'Saved conversation'
    )
    expect(wrapper.emitted('rename')).toBeUndefined()
  })
})
