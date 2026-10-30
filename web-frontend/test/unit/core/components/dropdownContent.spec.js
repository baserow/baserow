import { flushPromises } from '@vue/test-utils'
import Dropdown from '@baserow/modules/core/components/Dropdown'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('Dropdown custom content', () => {
  let testApp
  beforeEach(() => {
    testApp = new TestApp()
  })
  afterEach(() => testApp.afterEach())

  async function render(props = {}) {
    return await testApp.mount(Dropdown, {
      props,
      global: { stubs: { teleport: true } },
      slots: {
        display: '<span>Country</span>',
        content: `<template #content="{ close }">
          <form @submit.prevent="close">
            <label>Country <input aria-label="Country" /></label>
            <button type="submit">Apply</button>
          </form>
        </template>`,
      },
    })
  }

  test('keeps a custom form open until Apply, then restores trigger focus', async () => {
    const wrapper = await render()
    const trigger = wrapper.get('button.dropdown__selected')
    expect(trigger.attributes('aria-expanded')).toBe('false')
    await trigger.trigger('click')
    await flushPromises()
    expect(trigger.attributes('aria-expanded')).toBe('true')
    await wrapper.get('input').setValue('France')
    expect(wrapper.emitted('input')).toBeUndefined()
    expect(trigger.attributes('aria-expanded')).toBe('true')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(trigger.attributes('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(trigger.element)
    expect(wrapper.emitted('hide')).toHaveLength(1)
  })

  test('Escape closes custom content without taking over its other keys', async () => {
    const wrapper = await render()
    const trigger = wrapper.get('button.dropdown__selected')
    await trigger.trigger('click')
    await flushPromises()
    const event = new KeyboardEvent('keydown', {
      key: 'Enter',
      bubbles: true,
      cancelable: true,
    })
    wrapper.get('input').element.dispatchEvent(event)
    expect(event.defaultPrevented).toBe(false)
    await wrapper.get('input').trigger('keydown', { key: 'Escape' })
    await flushPromises()
    expect(trigger.attributes('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(trigger.element)
  })

  test.each([{ disabled: true }, { loading: true }])(
    'does not open when %j',
    async (props) => {
      const wrapper = await render(props)
      await wrapper.get('button.dropdown__selected').trigger('click')
      await flushPromises()
      expect(wrapper.find('form').exists()).toBe(false)
    }
  )

  test('allows beforeShow to cancel opening', async () => {
    const wrapper = await render({ beforeShow: () => false })
    await wrapper.get('button.dropdown__selected').trigger('click')
    await flushPromises()
    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.emitted('show')).toBeUndefined()
  })

  test('respects an explicit trigger tabindex', async () => {
    const wrapper = await render({ tabindex: -1 })
    expect(
      wrapper.get('button.dropdown__selected').attributes('tabindex')
    ).toBe('-1')
  })

  test('supports an external opener when showInput is false', async () => {
    const wrapper = await testApp.mount(
      {
        components: { Dropdown },
        template: `<div>
        <button @click="$refs.dropdown.show($event.currentTarget)">Open</button>
        <Dropdown ref="dropdown" :show-input="false">
          <template #content="{ close }">
            <button @click="close">Close</button>
          </template>
        </Dropdown>
      </div>`,
      },
      { global: { stubs: { teleport: true } } }
    )
    const opener = wrapper.get('button')
    await opener.trigger('click')
    await flushPromises()
    await wrapper.get('.context button').trigger('click')
    await flushPromises()
    expect(wrapper.get('.context').classes()).toContain('visibility-hidden')
    expect(document.activeElement).toBe(opener.element)
  })

  test('an outside click dismisses the panel without stealing focus', async () => {
    const wrapper = await render()
    const trigger = wrapper.get('button.dropdown__selected')
    await trigger.trigger('click')
    await flushPromises()
    const outside = document.createElement('button')
    document.body.append(outside)
    try {
      outside.focus()
      outside.click()
      await flushPromises()
      expect(trigger.attributes('aria-expanded')).toBe('false')
      expect(document.activeElement).toBe(outside)
      expect(wrapper.emitted('hide')).toHaveLength(1)
    } finally {
      outside.remove()
    }
  })
})
