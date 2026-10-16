import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import AgentConfigurationSidebar from '@baserow/modules/agent/components/AgentConfigurationSidebar'

describe('AgentConfigurationSidebar', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  test('keeps selector menus inside the viewport outside the scrolling form', async () => {
    const wrapper = await testApp.mount(AgentConfigurationSidebar, {
      props: {
        configuration: {
          name: 'Support agent',
          instructions: 'Be helpful.',
          provider_type: 'openai',
          model_identifier: 'model-one',
        },
        errors: {},
        enabledModels: { openai: ['model-one', 'model-two'] },
        editable: true,
      },
    })
    await wrapper
      .findAll('.agent-configuration__section')
      .find((button) => button.text().includes('agent.agentSettings'))
      .trigger('click')
    const [provider, model] = wrapper.findAll('.dropdown')
    let top = 80
    vi.spyOn(model.element, 'getBoundingClientRect').mockImplementation(
      () => new DOMRect(160, top, 360, 36)
    )

    await model.get('.dropdown__selected').trigger('click')
    await flushPromises()
    const menu = model.get('.dropdown__items')
    expect([menu.element.style.left, menu.element.style.top]).toEqual([
      '160px',
      '80px',
    ])
    top = window.innerHeight - 80
    window.dispatchEvent(new Event('resize'))
    await flushPromises()
    expect(menu.element.style.bottom).toBe('44px')
    await menu.get('.select__search-input').setValue('model-two')
    await menu.get('.select__search-input').trigger('keyup')
    await menu.get('.select__item.visible .select__item-link').trigger('click')

    expect(provider.get('.dropdown__items').classes()).toContain(
      'dropdown__items--fixed'
    )
    expect(wrapper.emitted('change')).toEqual([
      [{ model_identifier: 'model-two' }],
    ])
  })
})
