import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import AIProviderModelCombobox from '@baserow/modules/core/components/ai/AIProviderModelCombobox'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('AIProviderModelCombobox', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('supports keyboard selection from the known model suggestions', async () => {
    const wrapper = await testApp.mount(AIProviderModelCombobox, {
      props: {
        modelValue: '',
        suggestions: ['gpt-5.6', 'gpt-5.6-terra'],
      },
    })
    const input = wrapper.find('.form-input__input')

    await input.trigger('focus')
    expect(wrapper.findAll('[role="option"]')).toHaveLength(2)

    await input.trigger('keydown', { key: 'ArrowDown' })
    await input.trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('update:modelValue')).toContainEqual([
      'gpt-5.6-terra',
    ])
  })

  test('keeps custom identifiers editable when no suggestion matches', async () => {
    const wrapper = await testApp.mount(AIProviderModelCombobox, {
      props: {
        modelValue: '',
        suggestions: ['gpt-5.6'],
      },
    })
    const input = wrapper.find('.form-input__input')

    await input.trigger('focus')
    await input.setValue('custom-compatible-model')

    expect(wrapper.emitted('update:modelValue')).toContainEqual([
      'custom-compatible-model',
    ])
    await wrapper.setProps({ modelValue: 'custom-compatible-model' })
    expect(wrapper.findAll('[role="option"]')).toHaveLength(0)
    expect(wrapper.text()).toContain('aiProviderAdmin.modelDiscoveryNoMatch')
  })
})
